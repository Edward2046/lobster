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


@tool
def create_goal(goal: str, success_criteria: str = "", priority: int = 3) -> str:
    """Create or update an active goal in long-term planning memory.

    Args:
        goal: Goal description to track.
        success_criteria: Optional completion criteria.
        priority: Priority from 1 (highest) to 5 (lowest).
    """
    memory = get_memory_manager()
    memory.set_goal(goal=goal, success_criteria=success_criteria, priority=priority, status="active")
    return f"已记录目标：{goal}"


@tool
def list_active_goals(limit: int = 10) -> str:
    """List active goals currently tracked by Lobster.

    Args:
        limit: Maximum number of goals to return.
    """
    limit = max(1, min(limit, 20))
    memory = get_memory_manager()
    goals = memory.list_goals(limit=limit, status="active")
    if not goals:
        return "当前没有激活目标。"

    lines = [f"当前激活目标（共 {len(goals)} 条）：\n"]
    for index, goal in enumerate(goals, 1):
        criteria = goal["success_criteria"] or "未设置"
        lines.append(f"{index}. [P{goal['priority']}] {goal['goal']}")
        lines.append(f"   完成标准：{criteria}")
    return "\n".join(lines)


@tool
def complete_goal(goal: str) -> str:
    """Mark a tracked goal as completed.

    Args:
        goal: Goal description to mark as completed.
    """
    memory = get_memory_manager()
    updated = memory.update_goal_status(goal=goal, status="completed")
    if updated:
        return f"目标已完成：{goal}"
    return f"没有找到目标：{goal}"


@tool
def review_recent_reflections(limit: int = 5) -> str:
    """Review recent reflections so the agent can learn from prior outcomes.

    Args:
        limit: Maximum number of reflections to return.
    """
    limit = max(1, min(limit, 10))
    memory = get_memory_manager()
    reflections = memory.list_recent_reflections(limit=limit)
    if not reflections:
        return "还没有可回顾的反思记录。"

    lines = [f"最近反思（共 {len(reflections)} 条）：\n"]
    for index, reflection in enumerate(reflections, 1):
        lines.append(
            f"{index}. [{reflection['outcome']}] {reflection['question'][:60]} -> {reflection['lessons'][:120]}"
        )
    return "\n".join(lines)
