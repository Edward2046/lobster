# memory_tool.py — 记忆工具
#
# 让 Agent 能够主动查询历史对话和管理知识库

from smolagents import tool
from service.memory import get_memory_manager


@tool
def search_memory(keyword: str, limit: int = 10) -> str:
    """Search conversation history for messages containing a keyword.

    Use this when you need to recall what was discussed before about a specific topic.

    Args:
        keyword: The keyword to search for in conversation history.
        limit: Maximum number of results to return (1-50). Defaults to 10.
    """
    limit = max(1, min(limit, 50))
    memory = get_memory_manager()
    results = memory.search_conversations(keyword=keyword, limit=limit)

    if not results:
        return f"No conversation history found containing '{keyword}'."

    lines = [f"找到 {len(results)} 条包含 '{keyword}' 的历史对话：\n"]
    for i, conv in enumerate(results, 1):
        role_label = "用户" if conv["role"] == "user" else "我"
        timestamp = conv["timestamp"][:16]  # 只显示日期和时分
        lines.append(f"{i}. [{timestamp}] {role_label}: {conv['content'][:100]}")
        if len(conv['content']) > 100:
            lines.append("   ...")

    return "\n".join(lines)


@tool
def remember_fact(key: str, value: str) -> str:
    """Save an important fact or user preference to long-term memory.

    Use this when the user explicitly asks you to remember something,
    or when you learn an important preference/fact that should persist across conversations.

    Args:
        key: A short identifier for this fact (e.g., "user_language", "favorite_food").
        value: The fact or preference to remember.
    """
    memory = get_memory_manager()
    memory.save_knowledge(key=key, value=value)
    return f"已记住：{key} = {value}"


@tool
def recall_fact(key: str) -> str:
    """Retrieve a previously saved fact or preference from long-term memory.

    Args:
        key: The identifier of the fact to recall.
    """
    memory = get_memory_manager()
    value = memory.get_knowledge(key=key)

    if value is None:
        return f"没有找到关于 '{key}' 的记忆。"

    return f"{key}: {value}"


@tool
def list_all_facts(limit: int = 20) -> str:
    """List all facts and preferences stored in long-term memory.

    Args:
        limit: Maximum number of facts to return (1-50). Defaults to 20.
    """
    limit = max(1, min(limit, 50))
    memory = get_memory_manager()
    facts = memory.list_knowledge(limit=limit)

    if not facts:
        return "长期记忆中还没有保存任何事实。"

    lines = [f"长期记忆中的事实（共 {len(facts)} 条）：\n"]
    for i, fact in enumerate(facts, 1):
        updated = fact["updated_at"][:16]
        lines.append(f"{i}. {fact['key']}: {fact['value']}")
        lines.append(f"   (更新于 {updated})")

    return "\n".join(lines)


@tool
def forget_fact(key: str) -> str:
    """Delete a fact or preference from long-term memory.

    Args:
        key: The identifier of the fact to forget.
    """
    memory = get_memory_manager()
    deleted = memory.delete_knowledge(key=key)

    if deleted:
        return f"已忘记：{key}"
    else:
        return f"没有找到关于 '{key}' 的记忆，无需删除。"
