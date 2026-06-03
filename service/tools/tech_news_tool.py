# tech_news_tool.py — 全球科技资讯聚合工具
#
# 通过多源 RSS 聚合科技新闻，覆盖 TechCrunch / The Verge / Hacker News / Bloomberg Tech。
# 优先用稳定的 RSS 源，Bloomberg 直接 RSS 不可用时通过 Google News 代理。

import requests
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from smolagents import tool

from config import settings


# RSS 源配置：每个源给出 url + 显示名
_SOURCES: dict[str, dict] = {
    "techcrunch": {
        "url": "https://techcrunch.com/feed/",
        "name": "TechCrunch",
    },
    "theverge": {
        "url": "https://www.theverge.com/rss/index.xml",
        "name": "The Verge",
    },
    "hackernews": {
        "url": "https://hnrss.org/frontpage",
        "name": "Hacker News",
    },
    "bloomberg_tech": {
        # Bloomberg 直接 RSS 受限，用 Google News 关键词代理
        "url": "https://news.google.com/rss/search?q=site:bloomberg.com/news/articles+technology&hl=en-US&gl=US&ceid=US:en",
        "name": "Bloomberg Technology",
    },
    "arstechnica": {
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "name": "Ars Technica",
    },
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Atom namespace（The Verge 用的是 Atom 格式）
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _parse_feed(source_key: str, source_cfg: dict, limit: int) -> list[dict]:
    """拉取并解析单个 RSS/Atom 源，返回结构化条目列表。"""
    try:
        resp = requests.get(
            source_cfg["url"],
            headers=_HEADERS,
            timeout=settings.tool.HTTP_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return [{"_error": f"{source_cfg['name']} 抓取失败: {e}"}]

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        return [{"_error": f"{source_cfg['name']} 解析失败: {e}"}]

    entries: list[dict] = []

    # RSS 2.0：<rss><channel><item>
    items = root.findall("./channel/item")
    if items:
        for item in items[:limit]:
            entries.append({
                "source": source_cfg["name"],
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "pubdate": (item.findtext("pubDate") or "").strip(),
                "summary": (item.findtext("description") or "").strip()[:300],
            })
        return entries

    # Atom：<feed><entry>
    atom_entries = root.findall("atom:entry", _ATOM_NS)
    if atom_entries:
        for entry in atom_entries[:limit]:
            link_el = entry.find("atom:link", _ATOM_NS)
            link = link_el.get("href", "") if link_el is not None else ""
            entries.append({
                "source": source_cfg["name"],
                "title": (entry.findtext("atom:title", default="", namespaces=_ATOM_NS) or "").strip(),
                "link": link,
                "pubdate": (entry.findtext("atom:updated", default="", namespaces=_ATOM_NS) or "").strip(),
                "summary": (entry.findtext("atom:summary", default="", namespaces=_ATOM_NS) or "").strip()[:300],
            })
        return entries

    return [{"_error": f"{source_cfg['name']} 未识别的 feed 格式"}]


@tool
def get_tech_news(source: str = "all", limit: int = 15) -> str:
    """Get the latest technology news from major tech publications via RSS.

    Aggregates news from TechCrunch, The Verge, Hacker News, Bloomberg Technology,
    and Ars Technica. Use this to track tech industry events that could move
    tech stocks (NVDA, AAPL, MSFT, GOOGL, META, TSLA, AMZN, etc.).

    Args:
        source: News source. Options:
                'all' (all sources, default),
                'techcrunch', 'theverge', 'hackernews', 'bloomberg_tech', 'arstechnica'.
        limit: Items to fetch per source (1-30). Default 15.

    Returns:
        Formatted tech news headlines with source, title, pubdate, and link.
    """
    limit = max(1, min(limit, 30))

    if source != "all" and source not in _SOURCES:
        valid = ", ".join(["all"] + list(_SOURCES.keys()))
        return f"Invalid source '{source}'. Valid options: {valid}."

    targets = list(_SOURCES.items()) if source == "all" else [(source, _SOURCES[source])]

    # 并发拉取多个源
    all_entries: list[dict] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=len(targets)) as executor:
        future_map = {
            executor.submit(_parse_feed, key, cfg, limit): key
            for key, cfg in targets
        }
        for future in as_completed(future_map):
            results = future.result()
            for item in results:
                if "_error" in item:
                    errors.append(item["_error"])
                else:
                    all_entries.append(item)

    if not all_entries:
        return "未抓取到任何科技资讯\n" + "\n".join(errors)

    # 按 source 分组输出，便于 LLM 后续提炼
    lines = [f"科技资讯聚合（来源：{source}，共 {len(all_entries)} 条）\n"]
    if errors:
        lines.append("⚠️ 部分源抓取异常：")
        for err in errors:
            lines.append(f"  - {err}")
        lines.append("")

    by_source: dict[str, list[dict]] = {}
    for entry in all_entries:
        by_source.setdefault(entry["source"], []).append(entry)

    for src_name, items in by_source.items():
        lines.append(f"── {src_name}（{len(items)} 条）──")
        for i, item in enumerate(items, start=1):
            lines.append(f"{i}. {item['title']}")
            if item["pubdate"]:
                lines.append(f"   时间：{item['pubdate']}")
            if item["summary"]:
                lines.append(f"   摘要：{item['summary']}")
            if item["link"]:
                lines.append(f"   链接：{item['link']}")
            lines.append("")

    return "\n".join(lines).strip()
