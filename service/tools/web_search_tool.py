# web_search_tool.py — DuckDuckGo 网络搜索工具

from smolagents import tool


@tool
def search_web(query: str, max_results: int = 5) -> str:
    """Search the web with DuckDuckGo and return markdown results.

    Args:
        query: Search query in natural language.
        max_results: Maximum number of results to return.
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return "duckduckgo-search is not installed. Please install dependencies first."

    if max_results <= 0:
        return "max_results must be greater than 0."

    items = []
    try:
        with DDGS() as ddgs:
            for index, result in enumerate(ddgs.text(query, max_results=max_results), start=1):
                title = result.get("title") or "Untitled"
                url = result.get("href") or result.get("url") or ""
                summary = result.get("body") or "No summary available."
                items.append(f"{index}. [{title}]({url})\n   {summary}")
    except Exception as e:
        return f"Web search failed: {e}"

    if not items:
        return f"No web results found for '{query}'."
    return "\n\n".join(items)
