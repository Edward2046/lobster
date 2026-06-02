#!/usr/bin/env python3
"""
query_db.py — 数据库查询工具

快速查询 data/memory.db 和 data/tasks.db 的数据

用法：
  python scripts/query_db.py memory          # 查看记忆数据库概览
  python scripts/query_db.py tasks           # 查看任务数据库概览
  python scripts/query_db.py conversations   # 查看最近对话
  python scripts/query_db.py knowledge       # 查看知识库
  python scripts/query_db.py goals           # 查看目标
  python scripts/query_db.py reflections     # 查看反思记录
  python scripts/query_db.py episodes        # 查看情景记忆
  python scripts/query_db.py task-list       # 查看所有任务
"""

import sys
import sqlite3
from pathlib import Path

# 数据库路径
DB_DIR = Path(__file__).parent.parent / "data"
MEMORY_DB = DB_DIR / "memory.db"
TASKS_DB = DB_DIR / "tasks.db"
from pathlib import Path


def query_memory_overview():
    """查看 memory.db 概览"""
    conn = sqlite3.connect(MEMORY_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print("Memory Database 概览")
    print("=" * 60)

    # 对话记录统计
    cursor.execute("SELECT COUNT(*) as count FROM conversations")
    conv_count = cursor.fetchone()["count"]
    cursor.execute("SELECT COUNT(DISTINCT session_id) as count FROM conversations WHERE session_id IS NOT NULL")
    session_count = cursor.fetchone()["count"]
    print(f"\n【对话记录】{conv_count} 条 (会话数: {session_count})")

    cursor.execute("SELECT role, COUNT(*) as count FROM conversations GROUP BY role")
    for row in cursor.fetchall():
        print(f"  - {row['role']}: {row['count']} 条")

    # 知识库统计
    cursor.execute("SELECT COUNT(*) as count FROM knowledge WHERE archived = 0")
    knowledge_count = cursor.fetchone()["count"]
    print(f"\n【知识库】{knowledge_count} 条")

    cursor.execute("SELECT category, COUNT(*) as count FROM knowledge WHERE archived = 0 GROUP BY category")
    for row in cursor.fetchall():
        print(f"  - {row['category']}: {row['count']} 条")

    # 情景记忆统计
    cursor.execute("SELECT COUNT(*) as count FROM episodes")
    episodes_count = cursor.fetchone()["count"]
    print(f"\n【情景记忆】{episodes_count} 条")

    # 反思记录统计
    cursor.execute("SELECT COUNT(*) as count FROM reflections")
    reflections_count = cursor.fetchone()["count"]
    print(f"\n【反思记录】{reflections_count} 条")

    cursor.execute("SELECT outcome, COUNT(*) as count FROM reflections GROUP BY outcome")
    for row in cursor.fetchall():
        print(f"  - {row['outcome']}: {row['count']} 条")

    # 目标统计
    cursor.execute("SELECT COUNT(*) as count FROM goals")
    goals_count = cursor.fetchone()["count"]
    print(f"\n【目标】{goals_count} 条")

    cursor.execute("SELECT status, COUNT(*) as count FROM goals GROUP BY status")
    for row in cursor.fetchall():
        print(f"  - {row['status']}: {row['count']} 条")

    conn.close()


def query_conversations(limit=20):
    """查看最近对话"""
    conn = sqlite3.connect(MEMORY_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print(f"最近 {limit} 条对话")
    print("=" * 60)

    cursor.execute("""
        SELECT role, content, timestamp
        FROM conversations
        ORDER BY timestamp DESC, id DESC
        LIMIT ?
    """, (limit,))

    for row in cursor.fetchall():
        role_label = "用户" if row["role"] == "user" else "Agent"
        timestamp = row["timestamp"][:19]
        content = row["content"][:100] + "..." if len(row["content"]) > 100 else row["content"]
        print(f"\n[{timestamp}] {role_label}:")
        print(f"  {content}")

    conn.close()


def query_knowledge(limit=50):
    """查看知识库"""
    conn = sqlite3.connect(MEMORY_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print(f"知识库 (前 {limit} 条)")
    print("=" * 60)

    cursor.execute("""
        SELECT key, value, category, confidence, source, updated_at
        FROM knowledge
        WHERE archived = 0
        ORDER BY confidence DESC, updated_at DESC
        LIMIT ?
    """, (limit,))

    for i, row in enumerate(cursor.fetchall(), 1):
        print(f"\n{i}. [{row['category']}] {row['key']}")
        print(f"   值: {row['value']}")
        print(f"   置信度: {row['confidence']:.2f} | 来源: {row['source']} | 更新: {row['updated_at'][:19]}")

    conn.close()


def query_goals():
    """查看目标"""
    conn = sqlite3.connect(MEMORY_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print("目标列表")
    print("=" * 60)

    cursor.execute("""
        SELECT goal, status, priority, success_criteria, created_at, updated_at
        FROM goals
        ORDER BY status, priority ASC, updated_at DESC
    """)

    current_status = None
    for row in cursor.fetchall():
        if current_status != row["status"]:
            current_status = row["status"]
            print(f"\n【{current_status.upper()}】")

        criteria = row["success_criteria"] or "未设置"
        print(f"  P{row['priority']} {row['goal']}")
        print(f"      完成标准: {criteria}")
        print(f"      创建: {row['created_at'][:10]} | 更新: {row['updated_at'][:10]}")

    conn.close()


def query_reflections(limit=20):
    """查看反思记录"""
    conn = sqlite3.connect(MEMORY_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print(f"反思记录 (前 {limit} 条)")
    print("=" * 60)

    cursor.execute("""
        SELECT question, answer_summary, outcome, lessons, confidence, created_at
        FROM reflections
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))

    for i, row in enumerate(cursor.fetchall(), 1):
        print(f"\n{i}. [{row['outcome']}] {row['question'][:60]}")
        print(f"   回答: {row['answer_summary'][:80]}")
        print(f"   经验: {row['lessons'][:100]}")
        print(f"   置信度: {row['confidence']:.2f} | 时间: {row['created_at'][:19]}")

    conn.close()


def query_episodes(limit=20):
    """查看情景记忆"""
    conn = sqlite3.connect(MEMORY_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print(f"情景记忆 (前 {limit} 条)")
    print("=" * 60)

    cursor.execute("""
        SELECT summary, details, tags, importance, created_at
        FROM episodes
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))

    for i, row in enumerate(cursor.fetchall(), 1):
        import json
        tags = json.loads(row["tags"] or "[]")
        tags_str = ", ".join(tags) if tags else "无"
        print(f"\n{i}. {row['summary']}")
        print(f"   详情: {row['details'][:100]}")
        print(f"   标签: {tags_str} | 重要度: {row['importance']:.2f}")
        print(f"   时间: {row['created_at'][:19]}")

    conn.close()


def query_tasks_overview():
    """查看 tasks.db 概览"""
    conn = sqlite3.connect(TASKS_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print("Tasks Database 概览")
    print("=" * 60)

    # 任务统计
    cursor.execute("SELECT COUNT(*) as count FROM tasks")
    total_count = cursor.fetchone()["count"]
    print(f"\n【任务总数】{total_count} 个")

    cursor.execute("SELECT enabled, COUNT(*) as count FROM tasks GROUP BY enabled")
    for row in cursor.fetchall():
        status = "启用" if row["enabled"] else "禁用"
        print(f"  - {status}: {row['count']} 个")

    # 任务类型分布
    cursor.execute("SELECT task_type, COUNT(*) as count FROM tasks GROUP BY task_type")
    print(f"\n【任务类型】")
    for row in cursor.fetchall():
        print(f"  - {row['task_type']}: {row['count']} 个")

    cursor.execute("SELECT last_run_status, COUNT(*) as count FROM tasks WHERE last_run_status IS NOT NULL GROUP BY last_run_status")
    print(f"\n【执行状态】")
    for row in cursor.fetchall():
        print(f"  - {row['last_run_status']}: {row['count']} 个")

    conn.close()


def query_task_list():
    """查看所有任务"""
    import json as _json
    conn = sqlite3.connect(TASKS_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print("任务列表")
    print("=" * 60)

    cursor.execute("""
        SELECT name, schedule_expr, notify_channel, enabled,
               task_type, task_params,
               last_run_at, last_run_status, description, builtin
        FROM tasks
        ORDER BY enabled DESC, builtin DESC, name
    """)

    for row in cursor.fetchall():
        status = "✅" if row["enabled"] else "❌"
        last_run = row["last_run_at"][:19] if row["last_run_at"] else "未运行"
        last_status = row["last_run_status"] or "N/A"
        builtin_label = " [内置]" if row["builtin"] else ""

        # 解析任务参数
        try:
            params = _json.loads(row["task_params"] or "{}")
        except Exception:
            params = {}

        if row["task_type"] == "report":
            params_display = f"report_type={params.get('report_type', 'N/A')}"
        elif row["task_type"] == "custom":
            code_len = len(params.get("code", ""))
            params_display = f"code ({code_len} 字符)"
        else:
            params_display = str(params)

        print(f"\n{status} {row['name']}{builtin_label}")
        print(f"   描述: {row['description'] or 'N/A'}")
        print(f"   类型: {row['task_type']} | 参数: {params_display}")
        print(f"   调度: {row['schedule_expr']} → {row['notify_channel']}")
        print(f"   最后执行: {last_run} ({last_status})")

    conn.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1].lower()

    try:
        if command == "memory":
            query_memory_overview()
        elif command == "tasks":
            query_tasks_overview()
        elif command == "conversations":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            query_conversations(limit)
        elif command == "knowledge":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
            query_knowledge(limit)
        elif command == "goals":
            query_goals()
        elif command == "reflections":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            query_reflections(limit)
        elif command == "episodes":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            query_episodes(limit)
        elif command == "task-list":
            query_task_list()
        else:
            print(f"未知命令: {command}")
            print(__doc__)
    except FileNotFoundError as e:
        print(f"❌ 数据库文件不存在: {e}")
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
