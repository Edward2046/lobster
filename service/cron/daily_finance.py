#!/usr/bin/env python3
# cron/daily_finance.py — 每天 09:00 推送财经简报到微信
#
# crontab 配置：
#   0 9 * * * cd /Users/libing/workplaza/lobster && python cron/daily_finance.py

import sys
import os

from datetime import date
from service.tools.investing_news_tool import get_investing_news
from service.cron.notify import send_wxpusher


def build_report() -> tuple[str, str]:
    """拉取财经资讯，组装简报标题和正文。"""
    today = date.today().strftime("%Y年%m月%d日")
    title = f"📈 财经简报 · {today}"

    sections = []

    # 全部资讯 Top 8
    news_all = get_investing_news(category="all", limit=8)
    sections.append(news_all)

    # 外汇动态 Top 5
    news_forex = get_investing_news(category="forex", limit=5)
    sections.append("\n── 外汇动态 ──\n" + "\n".join(
        line for line in news_forex.splitlines()
        if not line.startswith("英为财经")  # 去掉重复的标题行
    ))

    content = f"{title}\n{'='*40}\n\n" + "\n\n".join(sections)
    return title, content


if __name__ == "__main__":
    print("正在生成财经简报...")
    title, content = build_report()
    print(content[:200], "...")

    ok = send_wxpusher(title, content)
    if ok:
        print("✅ 财经简报已推送到微信")
    else:
        print("❌ 推送失败")
        sys.exit(1)
