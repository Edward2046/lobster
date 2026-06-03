# reports/tech_news.py — 科技资讯简报生成模块
#
# 1. 通过 get_tech_news 聚合多源 RSS
# 2. 调用 LLM 提炼 3-5 条最可能影响美股科技板块的重磅信息
# 3. 输出带股票代码与潜在影响的简报

import os
from datetime import date

from config import settings
from service.tools.tech_news_tool import get_tech_news


_PROMPT_TEMPLATE = """你是资深美股科技板块分析师。下面是今天聚合的多源科技资讯原文：

{raw_news}

请从中提炼出 **3-5 条最可能影响美股科技板块的重磅信息**，按重要性排序。

输出格式（使用 Markdown，链接必须用 [文本](url) 形式以便手机点击跳转）：

### [排序]. [标题（中文一句话点出关键事件）]
- 来源：[来源]
- 关联标的：[股票代码列表，如 NVDA / AAPL / MSFT；若无明确标的则写 "板块整体"]
- 潜在影响：[一句话说明可能的多空方向与逻辑]
- [阅读原文]([新闻链接])

要求：
1. 只挑「能影响股价」的信号：财报、监管、产品发布、巨头动向、宏观、并购、芯片产业链。
2. 单纯的产品评测、博客观点、HN 讨论可以忽略。
3. **不要输出英文原标题**，把要点全部融进中文标题里。
4. 没找到 3 条以上重磅信息时，如实说明，不强凑数量。
5. 不同条目之间用一个空行分隔，整体保持简洁，方便手机阅读。
"""


def _refine_with_llm(raw_news: str) -> str:
    """用 LiteLLM 调用大模型提炼重磅信息。"""
    from litellm import completion

    api_key = settings.agent.DEEPSEEK_API_KEY or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return "⚠️ 未配置 DEEPSEEK_API_KEY，跳过 LLM 提炼，原始资讯如下：\n\n" + raw_news

    prompt = _PROMPT_TEMPLATE.format(raw_news=raw_news)

    try:
        resp = completion(
            model=settings.agent.MODEL_ID_FAST,
            messages=[{"role": "user", "content": prompt}],
            api_key=api_key,
            timeout=settings.agent.TIMEOUT * 2,  # 提炼任务多给点时间
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ LLM 提炼失败：{e}\n\n原始资讯如下：\n\n{raw_news}"


def build_report() -> tuple[str, str]:
    """拉取多源科技资讯并由 LLM 提炼重磅信息，组装简报。"""
    today = date.today().strftime("%Y年%m月%d日")
    title = f"🚀 科技资讯重磅速递 · {today}"

    raw_news = get_tech_news(source="all", limit=15)
    refined = _refine_with_llm(raw_news)

    # markdown 输出，由 wxpusher contentType=3 渲染
    content = f"# {title}\n\n{refined}"
    return title, content
