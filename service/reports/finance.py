# reports/finance.py — 财经简报生成模块

from datetime import date
from service.tools.investing_news_tool import get_investing_news


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
