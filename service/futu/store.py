"""按用户隔离的富途交易规则与成交记录。"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from config import settings

try:
    from service.tenant import get_current_user_id
except ImportError:  # 个人仓库尚未接入多租户
    def get_current_user_id() -> int:
        return 0

_ALLOWED_FIELDS = {
    "last_price",
    "open_price",
    "high_price",
    "low_price",
    "prev_close_price",
    "volume",
    "change_rate",
}
_ALLOWED_OPS = {"<=", ">=", "<", ">", "==", "!="}
_ALLOWED_SIDES = {"BUY", "SELL"}
_ALLOWED_ORDER_TYPES = {"MARKET", "LIMIT"}
_CODE_PREFIXES = ("US.", "HK.", "SH.", "SZ.")


def _user_id() -> int:
    return get_current_user_id()


def validate_rule_payload(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Rule requires a non-empty name.")

    code = str(payload.get("code") or "").strip().upper()
    if not any(code.startswith(prefix) for prefix in _CODE_PREFIXES):
        raise ValueError("code must look like US.AAPL, HK.00700, SH.600519, or SZ.000001.")

    side = str(payload.get("side") or "BUY").strip().upper()
    if side not in _ALLOWED_SIDES:
        raise ValueError("side must be BUY or SELL.")

    order_type = str(payload.get("order_type") or "MARKET").strip().upper()
    if order_type not in _ALLOWED_ORDER_TYPES:
        raise ValueError("order_type must be MARKET or LIMIT.")

    qty = float(payload.get("qty") or 0)
    if qty <= 0:
        raise ValueError("qty must be greater than 0.")

    price = payload.get("price")
    if order_type == "LIMIT":
        if price is None or float(price) <= 0:
            raise ValueError("LIMIT orders require a positive price.")
        price = float(price)
    else:
        price = float(price) if price not in (None, "") else None

    conditions = payload.get("conditions") or []
    if not isinstance(conditions, list) or not conditions:
        raise ValueError("conditions must be a non-empty list of {field, op, value}.")
    normalized_conditions = []
    for item in conditions:
        field = str(item.get("field") or "").strip()
        op = str(item.get("op") or "").strip()
        if field not in _ALLOWED_FIELDS:
            raise ValueError(f"Unsupported condition field '{field}'.")
        if op not in _ALLOWED_OPS:
            raise ValueError(f"Unsupported condition op '{op}'.")
        normalized_conditions.append({"field": field, "op": op, "value": float(item.get("value"))})

    cooldown = int(payload.get("cooldown_minutes") or 60)
    max_per_day = int(payload.get("max_trades_per_day") or 1)
    if cooldown < 0 or max_per_day < 1:
        raise ValueError("cooldown_minutes must be >= 0 and max_trades_per_day must be >= 1.")

    return {
        "name": name,
        "code": code,
        "side": side,
        "order_type": order_type,
        "qty": qty,
        "price": price,
        "conditions": normalized_conditions,
        "cooldown_minutes": cooldown,
        "max_trades_per_day": max_per_day,
        "enabled": 1 if payload.get("enabled", True) else 0,
        "note": str(payload.get("note") or "").strip(),
    }


class FutuRuleStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.futu.DB_PATH
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS futu_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    code TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    qty REAL NOT NULL,
                    price REAL,
                    conditions_json TEXT NOT NULL,
                    cooldown_minutes INTEGER NOT NULL,
                    max_trades_per_day INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, name)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS futu_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    rule_name TEXT NOT NULL,
                    code TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def upsert_rule(self, payload: dict[str, Any]) -> dict[str, Any]:
        rule = validate_rule_payload(payload)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO futu_rules (
                    user_id, name, code, side, order_type, qty, price, conditions_json,
                    cooldown_minutes, max_trades_per_day, enabled, note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, name) DO UPDATE SET
                    code=excluded.code,
                    side=excluded.side,
                    order_type=excluded.order_type,
                    qty=excluded.qty,
                    price=excluded.price,
                    conditions_json=excluded.conditions_json,
                    cooldown_minutes=excluded.cooldown_minutes,
                    max_trades_per_day=excluded.max_trades_per_day,
                    enabled=excluded.enabled,
                    note=excluded.note,
                    updated_at=excluded.updated_at
                """,
                (
                    _user_id(),
                    rule["name"],
                    rule["code"],
                    rule["side"],
                    rule["order_type"],
                    rule["qty"],
                    rule["price"],
                    json.dumps(rule["conditions"], ensure_ascii=False),
                    rule["cooldown_minutes"],
                    rule["max_trades_per_day"],
                    rule["enabled"],
                    rule["note"],
                    now,
                    now,
                ),
            )
        return self.get_rule(rule["name"])

    def get_rule(self, name: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM futu_rules WHERE user_id=? AND name=?",
                (_user_id(), name),
            ).fetchone()
        return self._row_to_rule(row) if row else None

    def list_rules(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM futu_rules WHERE user_id=?"
        args: list[Any] = [_user_id()]
        if enabled_only:
            sql += " AND enabled=1"
        sql += " ORDER BY name"
        with self._connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [self._row_to_rule(row) for row in rows]

    def set_enabled(self, name: str, enabled: bool) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE futu_rules SET enabled=?, updated_at=? WHERE user_id=? AND name=?",
                (1 if enabled else 0, datetime.now(timezone.utc).isoformat(), _user_id(), name),
            )
        return self.get_rule(name)

    def delete_rule(self, name: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM futu_rules WHERE user_id=? AND name=?",
                (_user_id(), name),
            )
            return cursor.rowcount > 0

    def record_event(self, rule_name: str, code: str, action: str, detail: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO futu_events (user_id, rule_name, code, action, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    _user_id(),
                    rule_name,
                    code,
                    action,
                    json.dumps(detail, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM futu_events WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (_user_id(), limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def count_rule_actions_since(self, rule_name: str, since: datetime) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n FROM futu_events
                WHERE user_id=? AND rule_name=? AND action IN ('order', 'signal')
                  AND created_at >= ?
                """,
                (_user_id(), rule_name, since.isoformat()),
            ).fetchone()
        return int(row["n"] if row else 0)

    def last_rule_action_at(self, rule_name: str) -> datetime | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT created_at FROM futu_events
                WHERE user_id=? AND rule_name=? AND action IN ('order', 'signal')
                ORDER BY id DESC LIMIT 1
                """,
                (_user_id(), rule_name),
            ).fetchone()
        if not row:
            return None
        try:
            return datetime.fromisoformat(row["created_at"])
        except ValueError:
            return None

    @staticmethod
    def _row_to_rule(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "code": row["code"],
            "side": row["side"],
            "order_type": row["order_type"],
            "qty": row["qty"],
            "price": row["price"],
            "conditions": json.loads(row["conditions_json"]),
            "cooldown_minutes": row["cooldown_minutes"],
            "max_trades_per_day": row["max_trades_per_day"],
            "enabled": bool(row["enabled"]),
            "note": row["note"],
        }


def day_window_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return current.replace(hour=0, minute=0, second=0, microsecond=0)


def within_cooldown(last_at: datetime | None, cooldown_minutes: int, now: datetime | None = None) -> bool:
    if last_at is None or cooldown_minutes <= 0:
        return False
    current = now or datetime.now(timezone.utc)
    if last_at.tzinfo is None:
        last_at = last_at.replace(tzinfo=timezone.utc)
    return current - last_at < timedelta(minutes=cooldown_minutes)
