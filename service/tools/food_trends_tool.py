# food_trends_tool.py — 餐饮趋势追踪工具
#
# 数据来源（均为公开 RSS，无需 API key）：
#   日本：SoraNews24        — 日本美食文化、新品、餐厅动态
#   韩国：That's / Koreaboo — 韩国餐饮文化、流行食品
#   中国：The Beijinger     — 北京/中国餐饮新动向
#         That's China      — 上海/全国餐饮大事件
#   行业：Food Dive         — 全球食品饮料行业动态
#         Nation's Restaurant News — 美国连锁餐饮风向标
#
# 过滤策略：
#   - 日本/韩国源本身聚焦美食，直接取最新 N 条
#   - 中国/行业综合源通过关键词过滤，只保留餐饮相关内容

import re
import requests
import xml.etree.ElementTree as ET
from smolagents import tool

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# 各地区 RSS 源配置
# filtered=True 表示需要关键词过滤（综合类媒体）
_SOURCES = {
    "japan": [
        {
            "url": "https://soranews24.com/feed/",
            "label": "SoraNews24（日本）",
            "filtered": False,
        },
    ],
    "korea": [
        {
            "url": "https://www.thatsmags.com/china/rss",
            "label": "That's（韩国/亚洲）",
            "filtered": True,
        },
    ],
    "china": [
        {
            "url": "https://36kr.com/feed-newsflash",
            "label": "36氪快讯（餐饮过滤）",
            "filtered": True,
        },
        {
            "url": "https://www.tmtpost.com/rss.xml",
            "label": "钛媒体（餐饮过滤）",
            "filtered": True,
        },
        {
            "url": "https://www.thebeijinger.com/rss.xml",
            "label": "The Beijinger（北京）",
            "filtered": True,
        },
        {
            "url": "https://www.thatsmags.com/china/rss",
            "label": "That's China（上海/全国）",
            "filtered": True,
        },
    ],
    "industry": [
        {
            "url": "https://www.fooddive.com/feeds/news/",
            "label": "Food Dive（全球食品行业）",
            "filtered": False,
        },
        {
            "url": "https://www.nrn.com/rss.xml",
            "label": "Nation's Restaurant News（连锁餐饮）",
            "filtered": False,
        },
    ],
}

# 餐饮相关关键词，用于过滤综合类媒体的文章
# 注意：避免使用单字关键词（如「茶」「酒」「奶」），这类词容易在综合财经新闻里误匹配
# （比如「贵州茅台」会命中「酒」）。中文用复合词或具体品牌名。
_FOOD_KEYWORDS = re.compile(
    r"food|restaurant|cafe|coffee|tea\b|drink|bar|dining|cuisine|chef|menu|"
    r"ramen|sushi|bbq|hotpot|noodle|dumpling|bubble tea|milk tea|snack|"
    r"bakery|dessert|pizza|burger|steak|seafood|vegan|brunch|lunch|dinner|"
    r"michelin|opening|closes|pop.?up|delivery|takeaway|takeout|"
    r"餐饮|餐厅|外卖|连锁|加盟|预制菜|饮品|奶茶|咖啡|火锅|烧烤|烤肉|拉面|寿司|"
    r"小吃|甜品|烘焙|轻食|茶饮|酒馆|快餐|网红店|开业|闭店|首店|新店|门店|"
    r"喜茶|瑞幸|霸王茶姬|蜜雪冰城|星巴克|海底捞|西贝|肯德基|麦当劳|塔斯汀|奈雪|"
    r"古茗|沪上阿姨|茶颜悦色|百胜|九毛九|呷哺|湊湊|半天妖|绝味|周黑鸭|蜀大侠|"
    r"米其林|黑珍珠|大众点评|小红书",
    re.IGNORECASE,
)


def _fetch_rss(url: str) -> list[ET.Element]:
    """拉取 RSS 并返回 <item> 列表，失败返回空列表。"""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        content = resp.content
        # RSS 常带自定义命名空间前缀（atom:、dc:、media: 等）。
        # 直接删 xmlns 声明会导致前缀 unbound，改为把带前缀的标签替换成无前缀版本，
        # 再删掉 xmlns 声明，这样 ElementTree 就能正常解析。
        content = re.sub(rb"<(/?)[\w]+:([\w]+)", rb"<\1\2", content)   # <atom:link> → <link>
        content = re.sub(rb'\s+xmlns(?::\w+)?="[^"]*"', b"", content)  # 删 xmlns 声明
        root = ET.fromstring(content)
        return root.findall(".//item")
    except Exception:
        return []


def _is_food_related(item: ET.Element) -> bool:
    """判断一条 RSS item 是否与餐饮相关。"""
    text = " ".join(filter(None, [
        item.findtext("title") or "",
        item.findtext("description") or "",
        item.findtext("category") or "",
    ]))
    return bool(_FOOD_KEYWORDS.search(text))


def _format_items(items: list[ET.Element], limit: int, filtered: bool) -> list[str]:
    """将 item 列表格式化为标题行，filtered=True 时先过滤。带链接以便 LLM 在简报中引用。"""
    if filtered:
        items = [i for i in items if _is_food_related(i)]
    lines = []
    for item in items[:limit]:
        title    = (item.findtext("title")   or "").strip()
        link     = (item.findtext("link")    or "").strip()
        pubdate  = (item.findtext("pubDate") or "").strip()
        date_short = pubdate[:16] if pubdate else ""
        line = f"• {title}"
        if date_short:
            line += f"  [{date_short}]"
        if link:
            line += f"\n  链接：{link}"
        lines.append(line)
    return lines


@tool
def get_food_trends(region: str = "all", limit: int = 5) -> str:
    """Get the latest food & restaurant trends from Japan, Korea, China, and global industry news.

    Aggregates RSS feeds from food media in each region. No API key required.

    Args:
        region: Region to fetch. Options:
                'japan'    — Japanese food culture & new openings (SoraNews24)
                'korea'    — Korean food trends (That's Asia)
                'china'    — China dining news (The Beijinger + That's China)
                'industry' — Global F&B industry (Food Dive + NRN)
                'all'      — All regions combined (default)
        limit: Number of articles per source (1-10). Defaults to 5.
    """
    limit = max(1, min(limit, 10))

    if region not in _SOURCES and region != "all":
        valid = ", ".join(f"'{k}'" for k in list(_SOURCES.keys()) + ["all"])
        return f"Invalid region '{region}'. Valid options: {valid}."

    # 确定要拉取的地区列表
    regions_to_fetch = list(_SOURCES.keys()) if region == "all" else [region]

    # 地区标题映射
    region_titles = {
        "japan":    "🇯🇵 日本餐饮风向",
        "korea":    "🇰🇷 韩国餐饮风向",
        "china":    "🇨🇳 中国餐饮新方向",
        "industry": "🌐 全球餐饮行业动态",
    }

    output_lines = []
    any_content = False

    for reg in regions_to_fetch:
        section_lines = [region_titles[reg]]
        sources = _SOURCES[reg]

        # 同一地区可能有多个源，去重（china 和 korea 共用 thatsmags）
        seen_urls: set[str] = set()
        for src in sources:
            url = src["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)

            items = _fetch_rss(url)
            formatted = _format_items(items, limit, src["filtered"])
            if formatted:
                section_lines.append(f"  [{src['label']}]")
                section_lines.extend(formatted)
                any_content = True
            else:
                section_lines.append(f"  [{src['label']}] 暂无相关内容")

        output_lines.append("\n".join(section_lines))
        output_lines.append("")  # 地区间空行

    if not any_content:
        return "No food trend content found. Please try again later."

    return "\n".join(output_lines).strip()
