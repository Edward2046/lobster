# futu_trading_tool.py — 富途规则交易工具

from __future__ import annotations

import json

from smolagents import tool

from config import settings
from service.futu.client import get_backend, normalize_code, resolve_trd_env
from service.futu.engine import evaluate_rules, place_order_safely
from service.futu.store import FutuRuleStore
from service.tools.notify_tool import send_notification_result


def _store() -> FutuRuleStore:
    return FutuRuleStore()


def format_rule_scan(result: dict) -> str:
    lines = [
        f"Futu scan: scanned={result.get('scanned', 0)} matched={result.get('matched', 0)} "
        f"auto_trade={result.get('auto_trade')} env={result.get('trd_env')}"
    ]
    for item in result.get("actions") or []:
        lines.append(
            f"- [{item.get('status')}] {item.get('rule')} {item.get('side')} "
            f"{item.get('qty')} {item.get('code')} @ {item.get('price')}"
        )
        if item.get("error"):
            lines.append(f"  error: {item['error']}")
    for item in result.get("skipped") or []:
        lines.append(f"- skip {item.get('rule')}: {item.get('reason')}")
    if result.get("message") and not result.get("actions"):
        lines.append(result["message"])
    return "\n".join(lines)


def notify_futu_actions(channel: str, result: dict) -> str:
    actions = result.get("actions") or []
    if not actions or channel.strip().lower() == "none":
        return "No Futu notification sent."
    title = f"🦞 富途规则{'成交' if result.get('auto_trade') else '信号'} · {result.get('matched', 0)} 条"
    content = format_rule_scan(result)
    notice = send_notification_result(channel, title, content)
    return notice["message"]


@tool
def get_futu_status() -> str:
    """Show Futu OpenD trading configuration (never prints the unlock password)."""
    try:
        env = resolve_trd_env()
    except ValueError as exc:
        env = f"invalid ({exc})"
    return (
        f"enabled={settings.futu.ENABLED}\n"
        f"host={settings.futu.HOST}:{settings.futu.PORT}\n"
        f"trd_env={env}\n"
        f"allow_live={settings.futu.ALLOW_LIVE}\n"
        f"auto_trade={settings.futu.AUTO_TRADE}\n"
        f"market={settings.futu.MARKET}\n"
        f"max_qty={settings.futu.MAX_QTY}\n"
        f"max_notional={settings.futu.MAX_NOTIONAL}\n"
        f"unlock_password_set={bool(settings.futu.UNLOCK_PASSWORD)}"
    )


@tool
def get_futu_quote(code: str) -> str:
    """Fetch a Futu market snapshot for one stock code.

    Args:
        code: Security code like US.AAPL or HK.00700.
    """
    try:
        symbol = normalize_code(code)
        snaps = get_backend().snapshots([symbol])
    except Exception as exc:
        return f"Futu quote failed: {exc}"
    if not snaps:
        return f"No snapshot for {symbol}."
    row = snaps[0]
    return (
        f"{row.get('code')} {row.get('name')}\n"
        f"last={row.get('last_price')} change_rate={row.get('change_rate')}\n"
        f"open={row.get('open_price')} high={row.get('high_price')} low={row.get('low_price')}\n"
        f"prev_close={row.get('prev_close_price')} volume={row.get('volume')}"
    )


@tool
def get_futu_positions() -> str:
    """List current Futu positions in the configured trade environment."""
    try:
        rows = get_backend().positions()
    except Exception as exc:
        return f"Futu positions failed: {exc}"
    if not rows:
        return "No Futu positions."
    lines = [f"{item['code']}: qty={item['qty']} sellable={item['can_sell_qty']} cost={item['cost_price']}" for item in rows]
    return "\n".join(lines)


@tool
def list_futu_rules() -> str:
    """List this user's Futu auto-trade rules."""
    rules = _store().list_rules()
    if not rules:
        return "No Futu rules yet. Use add_futu_rule with a JSON rule."
    lines = []
    for rule in rules:
        state = "on" if rule["enabled"] else "off"
        lines.append(
            f"- [{state}] {rule['name']}: {rule['side']} {rule['qty']} {rule['code']} "
            f"{rule['order_type']} if {rule['conditions']}"
        )
    return "\n".join(lines)


@tool
def add_futu_rule(rule_json: str) -> str:
    """Create or replace a Futu auto-trade rule for the current user.

    Args:
        rule_json: JSON object. Example:
            {"name":"buy-aapl-dip","code":"US.AAPL","side":"BUY","qty":1,"order_type":"MARKET",
             "conditions":[{"field":"last_price","op":"<=","value":180}],
             "cooldown_minutes":60,"max_trades_per_day":1,"note":"dip buy"}
            Supported condition fields: last_price, open_price, high_price, low_price,
            prev_close_price, volume, change_rate. Ops: <= >= < > == !=.
    """
    try:
        payload = json.loads(rule_json)
        rule = _store().upsert_rule(payload)
    except json.JSONDecodeError as exc:
        return f"Invalid rule JSON: {exc}"
    except Exception as exc:
        return f"Save Futu rule failed: {exc}"
    return f"Saved Futu rule `{rule['name']}` for {rule['side']} {rule['qty']} {rule['code']}."


@tool
def delete_futu_rule(name: str) -> str:
    """Delete a Futu auto-trade rule by name.

    Args:
        name: Rule name.
    """
    if _store().delete_rule(name.strip()):
        return f"Deleted Futu rule `{name}`."
    return f"Futu rule `{name}` not found."


@tool
def enable_futu_rule(name: str, enabled: bool = True) -> str:
    """Enable or disable a Futu auto-trade rule.

    Args:
        name: Rule name.
        enabled: True to enable, False to pause.
    """
    rule = _store().set_enabled(name.strip(), enabled)
    if not rule:
        return f"Futu rule `{name}` not found."
    state = "enabled" if rule["enabled"] else "paused"
    return f"Futu rule `{rule['name']}` is {state}."


@tool
def run_futu_rules(notify_channel: str = "none") -> str:
    """Evaluate enabled Futu rules against live quotes. Places orders only if FUTU_AUTO_TRADE=true.

    Args:
        notify_channel: 'wxpusher', 'feishu', or 'none'. Sends a push when a rule matches.
    """
    try:
        result = evaluate_rules()
    except Exception as exc:
        return f"Futu rule scan failed: {exc}"
    notice = notify_futu_actions(notify_channel, result)
    return f"{format_rule_scan(result)}\n{notice}"


@tool
def place_futu_order(
    code: str,
    side: str,
    qty: float,
    order_type: str = "MARKET",
    price: float = 0.0,
    dry_run: bool = True,
    notify_channel: str = "none",
) -> str:
    """Place a Futu order with quantity/notional caps. Default is dry_run=true.

    Args:
        code: Security code like US.AAPL.
        side: BUY or SELL.
        qty: Order quantity.
        order_type: MARKET or LIMIT.
        price: Limit price. Ignored for MARKET unless OpenD requires a reference price.
        dry_run: If true, only validate and quote, do not submit.
        notify_channel: 'wxpusher', 'feishu', or 'none'.
    """
    try:
        order_price = price if price else None
        placed = place_order_safely(
            code=code,
            side=side,
            qty=qty,
            price=order_price,
            order_type=order_type,
            dry_run=dry_run,
        )
    except Exception as exc:
        return f"Futu order failed: {exc}"
    text = json.dumps(placed, ensure_ascii=False)
    if notify_channel.strip().lower() != "none":
        title = f"🦞 富途下单{'预览' if dry_run else '提交'} · {placed['code']}"
        notice = send_notification_result(notify_channel, title, text)
        return f"{text}\n{notice['message']}"
    return text
