"""规则求值 + 风控下单。默认只发信号；AUTO_TRADE 打开后才真正下单。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from config import settings
from service.futu.client import FutuQuoteBackend, get_backend, normalize_code, resolve_trd_env
from service.futu.store import FutuRuleStore, day_window_start, within_cooldown

log = logging.getLogger("lobster.futu")

_OPS = {
    "<=": lambda left, right: left <= right,
    ">=": lambda left, right: left >= right,
    "<": lambda left, right: left < right,
    ">": lambda left, right: left > right,
    "==": lambda left, right: left == right,
    "!=": lambda left, right: left != right,
}


def match_conditions(snapshot: dict[str, Any], conditions: list[dict[str, Any]]) -> bool:
    for item in conditions:
        left = snapshot.get(item["field"])
        if left is None:
            return False
        if not _OPS[item["op"]](float(left), float(item["value"])):
            return False
    return True


def check_order_limits(*, code: str, qty: float, price: float) -> None:
    normalize_code(code)
    if qty <= 0:
        raise ValueError("qty must be greater than 0.")
    if qty > settings.futu.MAX_QTY:
        raise ValueError(f"qty {qty} exceeds FUTU_MAX_QTY={settings.futu.MAX_QTY}.")
    notional = qty * price
    if notional > settings.futu.MAX_NOTIONAL:
        raise ValueError(
            f"notional {notional:.2f} exceeds FUTU_MAX_NOTIONAL={settings.futu.MAX_NOTIONAL}."
        )


def place_order_safely(
    *,
    code: str,
    side: str,
    qty: float,
    price: float | None = None,
    order_type: str = "MARKET",
    backend: FutuQuoteBackend | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    symbol = normalize_code(code)
    side = side.strip().upper()
    order_type = order_type.strip().upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL.")
    if order_type not in {"MARKET", "LIMIT"}:
        raise ValueError("order_type must be MARKET or LIMIT.")

    backend = backend or get_backend()
    snaps = backend.snapshots([symbol])
    if not snaps:
        raise RuntimeError(f"No snapshot for {symbol}.")
    last_price = float(snaps[0]["last_price"])
    submit_price = float(price) if price not in (None, "") else last_price
    check_order_limits(code=symbol, qty=qty, price=submit_price)

    payload = {
        "code": symbol,
        "side": side,
        "qty": qty,
        "price": submit_price,
        "order_type": order_type,
        "last_price": last_price,
        "trd_env": resolve_trd_env(),
        "dry_run": dry_run,
    }
    if dry_run:
        payload["status"] = "dry_run"
        return payload

    if not settings.futu.ENABLED:
        raise RuntimeError("Futu trading is disabled. Set FUTU_ENABLED=true.")

    placed = backend.place_order(
        code=symbol,
        side=side,
        qty=qty,
        price=submit_price,
        order_type=order_type,
    )
    payload.update(placed)
    payload["status"] = "submitted"
    return payload


def evaluate_rules(
    *,
    store: FutuRuleStore | None = None,
    backend: FutuQuoteBackend | None = None,
    auto_trade: bool | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    store = store or FutuRuleStore()
    backend = backend or get_backend()
    auto_trade = settings.futu.AUTO_TRADE if auto_trade is None else auto_trade
    now = now or datetime.now(timezone.utc)

    rules = store.list_rules(enabled_only=True)
    if not rules:
        return {"scanned": 0, "matched": 0, "actions": [], "skipped": [], "message": "No enabled Futu rules."}

    codes = sorted({rule["code"] for rule in rules})
    snapshots = {item["code"]: item for item in backend.snapshots(codes)}
    positions = {}
    try:
        positions = {item["code"]: item for item in backend.positions()}
    except Exception as exc:
        log.warning("Skip position lookup: %s", exc)

    actions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for rule in rules:
        snap = snapshots.get(rule["code"])
        if not snap:
            skipped.append({"rule": rule["name"], "reason": f"No snapshot for {rule['code']}"})
            continue
        if not match_conditions(snap, rule["conditions"]):
            continue

        last_at = store.last_rule_action_at(rule["name"])
        if within_cooldown(last_at, rule["cooldown_minutes"], now=now):
            skipped.append({"rule": rule["name"], "reason": "cooldown"})
            continue
        today_count = store.count_rule_actions_since(rule["name"], day_window_start(now))
        if today_count >= rule["max_trades_per_day"]:
            skipped.append({"rule": rule["name"], "reason": "max_trades_per_day"})
            continue

        if rule["side"] == "SELL":
            held = float((positions.get(rule["code"]) or {}).get("can_sell_qty") or 0)
            if held < float(rule["qty"]):
                skipped.append({"rule": rule["name"], "reason": f"insufficient position ({held})"})
                continue

        submit_price = rule["price"] if rule["order_type"] == "LIMIT" else snap["last_price"]
        try:
            check_order_limits(code=rule["code"], qty=rule["qty"], price=float(submit_price))
        except ValueError as exc:
            skipped.append({"rule": rule["name"], "reason": str(exc)})
            continue

        event = {
            "rule": rule["name"],
            "code": rule["code"],
            "side": rule["side"],
            "qty": rule["qty"],
            "price": submit_price,
            "order_type": rule["order_type"],
            "snapshot": {k: snap.get(k) for k in ("last_price", "change_rate", "name")},
            "trd_env": resolve_trd_env() if settings.futu.ENABLED else "DISABLED",
        }

        if auto_trade:
            try:
                placed = place_order_safely(
                    code=rule["code"],
                    side=rule["side"],
                    qty=rule["qty"],
                    price=submit_price,
                    order_type=rule["order_type"],
                    backend=backend,
                    dry_run=False,
                )
                event["order"] = placed
                event["status"] = "order"
                store.record_event(rule["name"], rule["code"], "order", event)
            except Exception as exc:
                event["status"] = "error"
                event["error"] = str(exc)
                store.record_event(rule["name"], rule["code"], "error", event)
        else:
            event["status"] = "signal"
            store.record_event(rule["name"], rule["code"], "signal", event)

        actions.append(event)

    return {
        "scanned": len(rules),
        "matched": len(actions),
        "auto_trade": auto_trade,
        "trd_env": resolve_trd_env() if settings.futu.ENABLED else "DISABLED",
        "actions": actions,
        "skipped": skipped,
    }
