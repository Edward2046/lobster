#!/usr/bin/env python3
"""
migrate_tasks.py — 将现有 tasks 表迁移到新的结构化格式

迁移规则：
  - 内置任务（finance/food/earnings）→ task_type='report', task_params={"report_type": "..."}
  - 自定义任务 → task_type='custom', task_params={"code": "..."}

执行：python scripts/migrate_tasks.py
"""

import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "tasks.db"

# 内置任务名 → report_type 映射
BUILTIN_REPORT_MAPPING = {
    "finance": "finance",
    "food": "food_trends",
    "earnings": "earnings",
}


def migrate():
    if not DB_PATH.exists():
        print(f"❌ 数据库不存在: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 检查表结构
    columns = {row["name"] for row in cursor.execute("PRAGMA table_info(tasks)").fetchall()}

    # 添加新列（如果不存在）
    if "task_type" not in columns:
        print("📦 添加 task_type 列...")
        cursor.execute("ALTER TABLE tasks ADD COLUMN task_type TEXT NOT NULL DEFAULT 'custom'")

    if "task_params" not in columns:
        print("📦 添加 task_params 列...")
        cursor.execute("ALTER TABLE tasks ADD COLUMN task_params TEXT NOT NULL DEFAULT '{}'")

    # 检查是否还有 code 列（旧字段）
    has_code_column = "code" in columns

    if not has_code_column:
        print("ℹ️ 数据库已是新结构，无需迁移")
        conn.close()
        return

    print("\n🔄 开始迁移数据...")

    # 读取所有任务
    rows = cursor.execute("SELECT id, name, code, task_type, task_params FROM tasks").fetchall()

    migrated_count = 0
    for row in rows:
        task_id = row["id"]
        name = row["name"]
        code = row["code"]
        current_type = row["task_type"]
        current_params = row["task_params"]

        # 跳过已经迁移过的
        if current_type != "custom" or current_params != "{}":
            print(f"  ⏭️  跳过已迁移任务: {name}")
            continue

        # 判断任务类型
        if name in BUILTIN_REPORT_MAPPING:
            # 内置报告任务
            new_type = "report"
            new_params = {"report_type": BUILTIN_REPORT_MAPPING[name]}
            print(f"  ✅ 迁移内置任务: {name} → report({new_params['report_type']})")
        else:
            # 自定义任务
            new_type = "custom"
            new_params = {"code": code}
            print(f"  ✅ 迁移自定义任务: {name} → custom (代码长度: {len(code)} 字符)")

        cursor.execute(
            """
            UPDATE tasks
            SET task_type = ?, task_params = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (new_type, json.dumps(new_params, ensure_ascii=False), task_id),
        )
        migrated_count += 1

    # 删除旧的 code 列（SQLite 不直接支持 DROP COLUMN，需要重建表）
    print(f"\n🗑️  删除旧的 code 列...")
    cursor.execute("""
        CREATE TABLE tasks_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            schedule_expr TEXT NOT NULL,
            task_type TEXT NOT NULL DEFAULT 'custom',
            task_params TEXT NOT NULL DEFAULT '{}',
            notify_channel TEXT DEFAULT 'none',
            enabled INTEGER DEFAULT 1,
            builtin INTEGER DEFAULT 0,
            last_run_at TEXT,
            last_run_status TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        INSERT INTO tasks_new (
            id, name, description, schedule_expr,
            task_type, task_params,
            notify_channel, enabled, builtin,
            last_run_at, last_run_status, created_at, updated_at
        )
        SELECT id, name, description, schedule_expr,
               task_type, task_params,
               notify_channel, enabled, builtin,
               last_run_at, last_run_status, created_at, updated_at
        FROM tasks
    """)

    cursor.execute("DROP TABLE tasks")
    cursor.execute("ALTER TABLE tasks_new RENAME TO tasks")

    conn.commit()
    conn.close()

    print(f"\n✅ 迁移完成！共迁移 {migrated_count} 个任务")
    print("\n📊 新表结构:")
    print("  - id, name, description, schedule_expr")
    print("  - task_type (report/custom)")
    print("  - task_params (JSON)")
    print("  - notify_channel, enabled, builtin")
    print("  - last_run_at, last_run_status, created_at, updated_at")


if __name__ == "__main__":
    migrate()
