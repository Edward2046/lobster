import os
import sqlite3
from pathlib import Path


_DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "tasks.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    schedule_expr TEXT NOT NULL,
    code TEXT NOT NULL,
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


def _connect() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(_SCHEMA)


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def create_task_record(
    name: str,
    schedule_expr: str,
    code: str,
    notify_channel: str,
    description: str,
    *,
    enabled: int = 1,
    builtin: int = 0,
) -> dict:
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO tasks (name, description, schedule_expr, code, notify_channel, enabled, builtin)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, description, schedule_expr, code, notify_channel, enabled, builtin),
        )
        row = conn.execute("SELECT * FROM tasks WHERE name = ?", (name,)).fetchone()
    return row_to_dict(row)


def create_builtin_task_if_missing(
    name: str,
    schedule_expr: str,
    code: str,
    notify_channel: str,
    description: str,
) -> dict:
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO tasks (name, description, schedule_expr, code, notify_channel, enabled, builtin)
            VALUES (?, ?, ?, ?, ?, 1, 1)
            """,
            (name, description, schedule_expr, code, notify_channel),
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
        SELECT id, name, description, schedule_expr, notify_channel, enabled, builtin,
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
    allowed_fields = {"schedule_expr", "code", "notify_channel", "description", "enabled"}
    updates = {key: value for key, value in fields.items() if key in allowed_fields and value is not None}
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
