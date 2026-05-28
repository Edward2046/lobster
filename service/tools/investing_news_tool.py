# investing_news_tool.py — 英为财经（cn.investing.com）财经资讯工具
#
# 英为财经提供公开的 RSS feed，无需 API key，无需登录。
# 可用的 feed 端点：
#   /rss/news.rss          — 全部资讯
#   /rss/market_overview   — 市场概览
#   /rss/forex_rss.rss     — 外汇
#   /rss/crypto_rss.rss    — 加密货币

import requests
import xml.etree.ElementTree as ET
from smolagents import tool

# RSS feed 地址映射，key 作为 category 参数的合法值
_FEED_URLS = {
    "all":    "https://cn.investing.com/rss/news.rss",
    "forex":  "https://cn.investing.com/rss/forex_rss.rss",
    "crypto": "https://cn.investing.com/rss/crypto_rss.rss",
}

_HEADERS = {
    # 部分 CDN 节点会校验 User-Agent，模拟普通浏览器请求
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


@tool
def get_investing_news(category: str = "all", limit: int = 10) -> str:
    """Get the latest financial news headlines from cn.investing.com (英为财经).

    Args:
        category: News category to fetch. Options: 'all' (all news), 'forex' (外汇),
                  'crypto' (加密货币). Defaults to 'all'.
        limit: Number of news items to return (1-30). Defaults to 10.
    """
    # 参数校验
    if category not in _FEED_URLS:
        valid = ", ".join(f"'{k}'" for k in _FEED_URLS)
        return f"Invalid category '{category}'. Valid options: {valid}."
    limit = max(1, min(limit, 30))  # 限制在 1~30 条之间

    url = _FEED_URLS[category]
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return f"Failed to fetch news feed: {e}"

    # 解析 RSS XML
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        return f"Failed to parse RSS feed: {e}"

    # RSS 结构：<rss> → <channel> → <item>...
    items = root.findall("./channel/item")
    if not items:
        return "No news items found in the feed."

    lines = [f"英为财经 最新财经资讯（{category}，共 {min(limit, len(items))} 条）\n"]
    for i, item in enumerate(items[:limit], start=1):
        title   = (item.findtext("title")   or "").strip()
        pubdate = (item.findtext("pubDate") or "").strip()
        author  = (item.findtext("author")  or "").strip()
        link    = (item.findtext("link")    or "").strip()

        lines.append(f"{i}. [{pubdate}] {title}")
        if author:
            lines.append(f"   来源：{author}")
        if link:
            lines.append(f"   链接：{link}")
        lines.append("")  # 空行分隔

    return "\n".join(lines).strip()
