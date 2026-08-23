# reports/futu_scan.py — 定时扫描富途规则并在命中后推送

from service.futu.engine import evaluate_rules
from service.tools.futu_trading_tool import format_rule_scan


def build_report(params: dict | None = None) -> tuple[str | None, str | None]:
    """扫描当前用户规则。无命中时返回 (None, None)，调度器会跳过推送。"""
    result = evaluate_rules()
    actions = result.get("actions") or []
    if not actions:
        return None, None
    title = f"🦞 富途规则{'成交' if result.get('auto_trade') else '信号'} · {result.get('matched', 0)} 条"
    content = format_rule_scan(result)
    return title, content
