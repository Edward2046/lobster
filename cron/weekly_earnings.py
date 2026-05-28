#!/usr/bin/env python3
# cron/weekly_earnings.py — 每周一 08:00 推送一周财报日历到微信
#
# crontab 配置：
#   0 8 * * 1 cd /Users/libing/workplaza/lobster && python cron/weekly_earnings.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from datetime import date
from tools.earnings_calendar_tool import get_earnings_calendar
from cron.notify import send_wxpusher


def build_report() -> tuple[str, str]:
    """拉取未来 7 天财报日历，组装简报标题和正文。"""
    today = date.today()
    title = f"📊 本周财报日历 · {today.strftime('%Y年%m月%d日')}起"

    content_body = get_earnings_calendar(days=7)
    content = f"{title}\n{'='*40}\n\n{content_body}"
    return title, content


if __name__ == "__main__":
    print("正在生成本周财报日历...")
    title, content = build_report()
    print(content[:200], "...")

    ok = send_wxpusher(title, content)
    if ok:
        print("✅ 财报日历已推送到微信")
    else:
        print("❌ 推送失败")
        sys.exit(1)
