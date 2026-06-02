import os
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


_DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "tasks.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
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
);
"""


def get_db_path() -> Path:
    return Path(os.environ.get("LOBSTER_TASK_DB", _DEFAULT_DB_PATH))


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """确保表中存在指定列，不存在则添加（用于平滑迁移）"""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    columns = {row["name"] for row in rows}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db() -> None:
    with _connect() as conn:
        conn.execute(_SCHEMA)
        # 平滑迁移：为旧数据库添加新字段
        _ensure_column(conn, "tasks", "task_type", "TEXT NOT NULL DEFAULT 'custom'")
        _ensure_column(conn, "tasks", "task_params", "TEXT NOT NULL DEFAULT '{}'")


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def create_task_record(
    name: str,
    schedule_expr: str,
    task_type: str,
    task_params: dict,
    notify_channel: str,
    description: str,
    *,
    enabled: int = 1,
    builtin: int = 0,
) -> dict:
    init_db()
    params_json = json.dumps(task_params, ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO tasks (
                name, description, schedule_expr,
                task_type, task_params,
                notify_channel, enabled, builtin
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, description, schedule_expr, task_type, params_json, notify_channel, enabled, builtin),
        )
        row = conn.execute("SELECT * FROM tasks WHERE name = ?", (name,)).fetchone()
    return row_to_dict(row)


def create_builtin_task_if_missing(
    name: str,
    schedule_expr: str,
    task_type: str,
    task_params: dict,
    notify_channel: str,
    description: str,
) -> dict:
    init_db()
    params_json = json.dumps(task_params, ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO tasks (
                name, description, schedule_expr,
                task_type, task_params,
                notify_channel, enabled, builtin
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, 1)
            """,
            (name, description, schedule_expr, task_type, params_json, notify_channel),
        )
        row = conn.execute("SELECT * FROM tasks WHERE name = ?", (name,)).fetchone()
    return row_to_dict(row)


def get_task_record(name: str) -> dict | None:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE name = ?", (name,)).fetchone()
    return row_to_dict(row)


def list_task_records(*, enabled_only: bool = False) -> list[dict]:
    init_db()
    query = """
        SELECT id, name, description, schedule_expr,
               task_type, task_params,
               notify_channel, enabled, builtin,
               last_run_at, last_run_status, created_at, updated_at
        FROM tasks
    """
    params: tuple = ()
    if enabled_only:
        query += " WHERE enabled = 1"
    query += " ORDER BY builtin DESC, name ASC"
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def update_task_record(name: str, **fields) -> dict | None:
    allowed_fields = {"schedule_expr", "task_type", "task_params", "notify_channel", "description", "enabled"}
    updates = {key: value for key, value in fields.items() if key in allowed_fields and value is not None}

    # 如果 task_params 是 dict，序列化为 JSON
    if "task_params" in updates and isinstance(updates["task_params"], dict):
        updates["task_params"] = json.dumps(updates["task_params"], ensure_ascii=False)

    if not updates:
        return get_task_record(name)

    assignments = ", ".join(f"{key} = ?" for key in updates)
    params = [*updates.values(), name]

    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            f"""
            UPDATE tasks
            SET {assignments},
                updated_at = datetime('now')
            WHERE name = ?
            """,
            params,
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM tasks WHERE name = ?", (name,)).fetchone()
    return row_to_dict(row)


def delete_task_record(name: str) -> bool:
    init_db()
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE name = ?", (name,))
    return cursor.rowcount > 0


def update_task_run_status(name: str, *, last_run_at: str, last_run_status: str) -> dict | None:
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE tasks
            SET last_run_at = ?, last_run_status = ?, updated_at = datetime('now')
            WHERE name = ?
            """,
            (last_run_at, last_run_status, name),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM tasks WHERE name = ?", (name,)).fetchone()
    return row_to_dict(row)
