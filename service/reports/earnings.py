# reports/earnings.py — 财报日历生成模块

from datetime import date
from service.tools.earnings_calendar_tool import get_earnings_calendar


def build_report() -> tuple[str, str]:
    """拉取未来 7 天财报日历，组装简报标题和正文。"""
    today = date.today()
    title = f"📊 本周财报日历 · {today.strftime('%Y年%m月%d日')}起"

    content_body = get_earnings_calendar(days=7)
    content = f"{title}\n{'='*40}\n\n{content_body}"
    return title, content
