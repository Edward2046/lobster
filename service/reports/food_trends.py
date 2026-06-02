# reports/food_trends.py — 餐饮趋势简报生成模块

import os
from datetime import date
from openai import OpenAI
from service.tools.food_trends_tool import get_food_trends

_client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

_SYSTEM_PROMPT = """你是一位专注餐饮行业的资深分析师，擅长从碎片化资讯中提炼趋势信号、识别商业机会。
你的简报风格：信息密度高、有具体品牌/数据支撑、结论直接、对从业者有实际参考价值。"""

_USER_PROMPT_TEMPLATE = """以下是今日从多个渠道抓取的餐饮资讯原始标题，按地区分组：

{raw_data}

请基于以上内容，生成一份今日餐饮趋势简报，严格按照以下格式输出，不要添加任何额外说明：

📌 T-1 餐饮大事件
（3-5条，今日最重要的行业事件，要有具体品牌/机构名称，每条以 • 开头）

💡 行业机会
（3-5条，从事件中提炼出的商业机会或策略信号，每条以 • 开头）

🇯🇵🇰🇷 日韩餐饮趋势
（4-6条，聚焦日本和韩国的具体品牌动态、流行品类、消费行为变化，每条以 • 开头，注明国家）

🇨🇳 中国餐饮新方向
（3-5条，中国市场的新开品牌、新品类、消费趋势，每条以 • 开头）

🎯 重点关注
（3条，用①②③编号，每条一个值得持续跟踪的趋势方向，加破折号说明原因）

注意：
- 有具体数据或品牌名的优先写入，不要泛泛而谈
- 如果某个板块原始数据不足，可以标注"今日数据有限"，不要编造内容
- 全部用中文输出"""


def _collect_raw_data() -> str:
    """拉取所有地区原始标题，拼成一个字符串供 AI 分析。"""
    region_labels = {
        "japan":    "【日本】",
        "korea":    "【韩国/亚洲】",
        "china":    "【中国】",
        "industry": "【全球行业】",
    }
    parts = []
    for region, label in region_labels.items():
        raw = get_food_trends(region=region, limit=8)
        if raw and "No food trend" not in raw:
            parts.append(f"{label}\n{raw}")
    return "\n\n".join(parts)


def _generate_report(raw_data: str) -> str:
    """将原始标题数据交给 DeepSeek 生成结构化简报。"""
    resp = _client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": _USER_PROMPT_TEMPLATE.format(raw_data=raw_data)},
        ],
        max_tokens=1000,
        temperature=0.6,
    )
    return resp.choices[0].message.content.strip()


def build_report() -> tuple[str, str]:
    today = date.today()
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday  = weekdays[today.weekday()]
    title    = f"🍜 餐饮趋势简报 | {today.month}月{today.day}日（{weekday}）"

    raw_data = _collect_raw_data()
    content  = _generate_report(raw_data)
    return title, content
