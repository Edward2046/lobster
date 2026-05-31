# web_search_tool.py — Tavily 网络搜索工具

import os

from smolagents import tool


def _create_tavily_client(api_key: str):
    from tavily import TavilyClient

    return TavilyClient(api_key=api_key)


@tool
def search_web(query: str, max_results: int = 5) -> str:
    """Search the web with Tavily and return markdown results.

    Args:
        query: Search query in natural language.
        max_results: Maximum number of results to return.
    """
    if max_results <= 0:
        return "max_results must be greater than 0."

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "TAVILY_API_KEY is not set. Please set it in your environment."

    try:
        client = _create_tavily_client(api_key)
        response = client.search(query, max_results=max_results)
    except ImportError:
        return "tavily-python is not installed. Please install dependencies first."
    except Exception as e:
        return f"Web search failed with Tavily: {e}"

    results = response.get("results") if isinstance(response, dict) else None
    if not results:
        return f"No web results found for '{query}'."

    items = []
    for index, result in enumerate(results, start=1):
        title = result.get("title") or "Untitled"
        url = result.get("url") or ""
        summary = result.get("content") or result.get("snippet") or "No summary available."
        items.append(f"{index}. [{title}]({url})\n   {summary}")
    return "\n\n".join(items)
