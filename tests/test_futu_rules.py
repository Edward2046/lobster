import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import settings
from service.futu.engine import evaluate_rules, match_conditions, place_order_safely
from service.futu.store import FutuRuleStore, validate_rule_payload


class FakeFutuBackend:
    def __init__(self, snapshots=None, positions=None):
        self.snapshots_data = snapshots or []
        self.positions_data = positions or []
        self.orders = []

    def snapshots(self, codes):
        wanted = set(codes)
        return [row for row in self.snapshots_data if row["code"] in wanted]

    def positions(self):
        return list(self.positions_data)

    def account(self):
        return {"cash": 10000}

    def place_order(self, *, code, side, qty, price, order_type):
        order = {
            "order_id": f"fake-{len(self.orders) + 1}",
            "code": code,
            "side": side,
            "qty": qty,
            "price": price,
            "order_type": order_type,
        }
        self.orders.append(order)
        return order


class FutuRuleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = FutuRuleStore(db_path=Path(self.temp_dir.name) / "futu.db")
        self.futu_patches = [
            patch.object(settings.futu, "ENABLED", True),
            patch.object(settings.futu, "TRD_ENV", "SIMULATE"),
            patch.object(settings.futu, "ALLOW_LIVE", False),
            patch.object(settings.futu, "AUTO_TRADE", False),
            patch.object(settings.futu, "MAX_QTY", 10),
            patch.object(settings.futu, "MAX_NOTIONAL", 2000.0),
        ]
        for item in self.futu_patches:
            item.start()

    def tearDown(self):
        for item in self.futu_patches:
            item.stop()
        self.temp_dir.cleanup()

    def test_validate_rule_requires_code_prefix_and_conditions(self):
        with self.assertRaises(ValueError):
            validate_rule_payload({"name": "bad", "code": "AAPL", "qty": 1, "conditions": [{"field": "last_price", "op": "<=", "value": 1}]})
        rule = validate_rule_payload(
            {
                "name": "buy-aapl-dip",
                "code": "us.aapl",
                "qty": 1,
                "conditions": [{"field": "last_price", "op": "<=", "value": 180}],
            }
        )
        self.assertEqual(rule["code"], "US.AAPL")
        self.assertEqual(rule["side"], "BUY")

    def test_match_conditions(self):
        snap = {"last_price": 170.0, "change_rate": -0.04}
        self.assertTrue(
            match_conditions(
                snap,
                [{"field": "last_price", "op": "<=", "value": 180}, {"field": "change_rate", "op": "<", "value": -0.03}],
            )
        )
        self.assertFalse(match_conditions(snap, [{"field": "last_price", "op": ">=", "value": 180}]))

    def test_evaluate_emits_signal_without_auto_trade(self):
        self.store.upsert_rule(
            {
                "name": "buy-aapl-dip",
                "code": "US.AAPL",
                "qty": 1,
                "conditions": [{"field": "last_price", "op": "<=", "value": 180}],
            }
        )
        backend = FakeFutuBackend(snapshots=[{"code": "US.AAPL", "last_price": 170.0, "name": "Apple", "change_rate": -0.02}])
        result = evaluate_rules(store=self.store, backend=backend, auto_trade=False)
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["actions"][0]["status"], "signal")
        self.assertEqual(backend.orders, [])

    def test_evaluate_places_order_when_auto_trade_enabled(self):
        self.store.upsert_rule(
            {
                "name": "buy-aapl-dip",
                "code": "US.AAPL",
                "qty": 2,
                "conditions": [{"field": "last_price", "op": "<=", "value": 180}],
            }
        )
        backend = FakeFutuBackend(snapshots=[{"code": "US.AAPL", "last_price": 170.0, "name": "Apple", "change_rate": 0}])
        result = evaluate_rules(store=self.store, backend=backend, auto_trade=True)
        self.assertEqual(result["actions"][0]["status"], "order")
        self.assertEqual(backend.orders[0]["qty"], 2)
        self.assertEqual(backend.orders[0]["side"], "BUY")

    def test_cooldown_skips_second_match(self):
        self.store.upsert_rule(
            {
                "name": "buy-aapl-dip",
                "code": "US.AAPL",
                "qty": 1,
                "cooldown_minutes": 60,
                "conditions": [{"field": "last_price", "op": "<=", "value": 180}],
            }
        )
        backend = FakeFutuBackend(snapshots=[{"code": "US.AAPL", "last_price": 170.0, "name": "Apple", "change_rate": 0}])
        first = evaluate_rules(store=self.store, backend=backend, auto_trade=False)
        second = evaluate_rules(store=self.store, backend=backend, auto_trade=False)
        self.assertEqual(first["matched"], 1)
        self.assertEqual(second["matched"], 0)
        self.assertEqual(second["skipped"][0]["reason"], "cooldown")

    def test_qty_cap_blocks_order(self):
        with self.assertRaises(ValueError):
            place_order_safely(
                code="US.AAPL",
                side="BUY",
                qty=99,
                price=100,
                backend=FakeFutuBackend(snapshots=[{"code": "US.AAPL", "last_price": 100.0}]),
                dry_run=True,
            )

    def test_live_env_requires_allow_live(self):
        with patch.object(settings.futu, "TRD_ENV", "REAL"), patch.object(settings.futu, "ALLOW_LIVE", False):
            from service.futu.client import resolve_trd_env

            with self.assertRaises(ValueError):
                resolve_trd_env()


if __name__ == "__main__":
    unittest.main()
