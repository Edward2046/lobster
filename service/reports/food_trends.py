# reports/food_trends.py — 餐饮趋势简报生成模块
#
# 输出 Markdown 格式，配合 wxpusher contentType=3 渲染：
# - 链接用 [文本](url)，手机点击直跳
# - 去掉无意义的英文原标题，要点融进中文
# - 简报结构精简，方便手机阅读

import os
from datetime import date
from openai import OpenAI

from config import settings
from service.tools.food_trends_tool import get_food_trends


_client = OpenAI(
    api_key=settings.agent.DEEPSEEK_API_KEY or os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

_SYSTEM_PROMPT = """你是一位专注中国餐饮市场的资深分析师，深谙国内连锁品牌、网红餐饮、消费趋势，
也熟悉小红书、大众点评、微博等平台的口碑动向。你的简报风格：信息密度高、有具体品牌/数据支撑、
结论直接、对从业者有实际参考价值。"""

_USER_PROMPT_TEMPLATE = """以下是今日从多渠道抓取的餐饮资讯（含原始标题与链接），按地区分组：

{raw_data}

请基于以上内容生成一份**以国内为重点**的餐饮趋势简报，**严格按照下方 Markdown 格式输出**，
不要添加任何额外说明、不要保留英文原标题。链接必须用 Markdown 格式 `[阅读](url)` 才能在手机上点击跳转。

### 🔥 国内网红品牌动态
（4-6 条国内网红/连锁品牌的最新动作：新品发布、扩张/闭店、营销事件、跨界联名等。
每条用 `- ` 开头：`- **[品牌名]** ｜ [中文一句话动态] · [阅读](url)`，没有可靠链接则省略 `· [阅读](...)`。
品牌优先级：喜茶/瑞幸/霸王茶姬/蜜雪冰城/海底捞/星巴克/奈雪/古茗/塔斯汀/西贝 等头部连锁。
今日资讯里提及的国内品牌都要尽量覆盖，没有就如实说明）

### 🏆 口碑爆棚餐馆 Top 5
（基于今日资讯+小红书/大众点评/微博的常见讨论度，给出 5 家近期口碑火爆的餐馆。
每条格式：`1. **[餐馆名]**（[城市] · [品类]）— [一句话亮点：招牌菜 / 人均 / 排队情况 / 媒体推荐]`
说明：这一栏不强求今日资讯里出现，可以基于行业常识与近期讨论度给出，但需在末尾加一行
`> 💡 数据综合自媒体公开报道与平台讨论度，建议探店前查阅最新点评。`）

### 📌 行业大事件
（3-5 条今日最重要的行业事件：融资、上市、并购、监管、行业报告等。
每条用 `- ` 开头，需含具体品牌/机构名，能配链接的配链接 `· [阅读](url)`）

### 💡 行业机会
（3-5 条从今日事件提炼的商业机会或策略信号，每条用 `- ` 开头，纯中文，无需链接）

### 🌏 海外参考
（4-6 条精选的日韩/全球餐饮动态，重点选有「可借鉴回国内」价值的内容。
每条用 `- ` 开头并加国旗，能配链接的配链接：`- 🇯🇵 [中文要点] · [阅读](url)`）

### 🎯 重点关注
（3 条值得持续跟踪的趋势方向，用 `1.` `2.` `3.` 编号，破折号说明原因，无需链接）

要求：
1. 全部中文输出，不要保留英文原标题。
2. 国内板块写不出实质内容时如实写「今日国内资讯有限，重点关注海外参考板块」，不要凑数。
3. Top 5 餐馆即使资讯里没有也要给出，可基于行业常识，但要在末尾加免责说明。
4. 链接必须是 `[阅读](url)` 格式，单独一行只放链接的不要写。
"""


def _collect_raw_data() -> str:
    """拉取所有地区原始标题，国内置顶，方便 LLM 重点利用。"""
    region_labels = [
        ("china",    "【中国（重点）】"),
        ("industry", "【全球行业】"),
        ("japan",    "【日本】"),
        ("korea",    "【韩国/亚洲】"),
    ]
    parts = []
    for region, label in region_labels:
        # 国内多源，多拉一些条目，确保有足够素材给 LLM
        limit = 10 if region == "china" else 6
        raw = get_food_trends(region=region, limit=limit)
        if raw and "No food trend" not in raw:
            parts.append(f"{label}\n{raw}")
    return "\n\n".join(parts)


def _generate_report(raw_data: str) -> str:
    """将原始标题数据交给 DeepSeek 生成结构化 Markdown 简报。"""
    resp = _client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": _USER_PROMPT_TEMPLATE.format(raw_data=raw_data)},
        ],
        max_tokens=2000,
        temperature=0.6,
    )
    return resp.choices[0].message.content.strip()


def build_report() -> tuple[str, str]:
    today = date.today()
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday  = weekdays[today.weekday()]
    title    = f"🍜 餐饮趋势简报 | {today.month}月{today.day}日（{weekday}）"

    raw_data = _collect_raw_data()
    body = _generate_report(raw_data)
    content = f"# {title}\n\n{body}"
    return title, content
