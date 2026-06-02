"""
memory.py — Agent 记忆管理模块

提供多层记忆：
  1. 短期记忆：最近对话
  2. 语义记忆：结构化事实与偏好
  3. 情景记忆：关键任务/事件摘要
  4. 反思记忆：每轮执行后的经验总结
  5. 目标记忆：当前正在追踪的长期目标

存储：SQLite 数据库（memory.db）
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from typing import Iterable, Optional


DB_PATH = Path(__file__).parent.parent / "memory.db"
_TOKEN_RE = re.compile(r"[0-9a-zA-Z_\u4e00-\u9fff]+")


def _tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in _TOKEN_RE.findall(text.lower()):
        if len(token) <= 1 or token in {"the", "and", "for", "that", "this", "with"}:
            continue
        tokens.add(token)
        if re.search(r"[\u4e00-\u9fff]", token):
            if len(token) == 2:
                tokens.add(token)
            else:
                tokens.update(token[index : index + 2] for index in range(len(token) - 1))
    return tokens


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


class MemoryManager:
    """记忆管理器，负责多层记忆的存储、检索与上下文组装。"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _get_columns(self, conn: sqlite3.Connection, table_name: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {row["name"] for row in rows}

    def _ensure_column(self, conn: sqlite3.Connection, table_name: str, column_name: str, ddl: str) -> None:
        if column_name not in self._get_columns(conn, table_name):
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    old_value TEXT NOT NULL,
                    new_value TEXT NOT NULL,
                    changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    source TEXT DEFAULT 'manual'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    summary TEXT NOT NULL,
                    details TEXT NOT NULL,
                    tags TEXT DEFAULT '[]',
                    importance REAL DEFAULT 0.5,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_accessed_at DATETIME
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reflections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    answer_summary TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    lessons TEXT NOT NULL,
                    confidence REAL DEFAULT 0.7,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    priority INTEGER NOT NULL DEFAULT 3,
                    success_criteria TEXT NOT NULL DEFAULT '',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            self._ensure_column(conn, "knowledge", "category", "TEXT DEFAULT 'semantic'")
            self._ensure_column(conn, "knowledge", "confidence", "REAL DEFAULT 0.8")
            self._ensure_column(conn, "knowledge", "source", "TEXT DEFAULT 'manual'")
            self._ensure_column(conn, "knowledge", "access_count", "INTEGER DEFAULT 0")
            self._ensure_column(conn, "knowledge", "last_accessed_at", "DATETIME")
            self._ensure_column(conn, "knowledge", "archived", "INTEGER DEFAULT 0")

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversations_timestamp
                ON conversations(timestamp DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversations_session
                ON conversations(session_id, timestamp DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_updated
                ON knowledge(updated_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_episodes_created
                ON episodes(created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reflections_created
                ON reflections(created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_goals_status_priority
                ON goals(status, priority ASC, updated_at DESC)
                """
            )

    def save_conversation(self, role: str, content: str, session_id: Optional[str] = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )

    def get_recent_conversations(self, limit: int = 10, session_id: Optional[str] = None) -> list[dict]:
        with self._connect() as conn:
            if session_id:
                rows = conn.execute(
                    """
                    SELECT role, content, timestamp
                    FROM conversations
                    WHERE session_id = ?
                    ORDER BY timestamp DESC, id DESC
                    LIMIT ?
                    """,
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT role, content, timestamp
                    FROM conversations
                    ORDER BY timestamp DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def search_conversations(self, keyword: str, limit: int = 20, session_id: Optional[str] = None) -> list[dict]:
        search_pattern = f"%{keyword}%"
        with self._connect() as conn:
            if session_id:
                rows = conn.execute(
                    """
                    SELECT role, content, timestamp
                    FROM conversations
                    WHERE session_id = ? AND content LIKE ?
                    ORDER BY timestamp DESC, id DESC
                    LIMIT ?
                    """,
                    (session_id, search_pattern, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT role, content, timestamp
                    FROM conversations
                    WHERE content LIKE ?
                    ORDER BY timestamp DESC, id DESC
                    LIMIT ?
                    """,
                    (search_pattern, limit),
                ).fetchall()
        return [dict(row) for row in rows]

    def save_knowledge(
        self,
        key: str,
        value: str,
        *,
        category: str = "semantic",
        confidence: float = 0.8,
        source: str = "manual",
    ) -> None:
        normalized_key = key.strip()
        normalized_value = value.strip()
        normalized_category = category.strip() or "semantic"
        normalized_source = source.strip() or "manual"
        normalized_confidence = _clamp(confidence, 0.0, 1.0)

        with self._connect() as conn:
            current = conn.execute(
                "SELECT value FROM knowledge WHERE key = ?",
                (normalized_key,),
            ).fetchone()
            if current and current["value"] != normalized_value:
                conn.execute(
                    """
                    INSERT INTO knowledge_revisions (key, old_value, new_value, source)
                    VALUES (?, ?, ?, ?)
                    """,
                    (normalized_key, current["value"], normalized_value, normalized_source),
                )
            conn.execute(
                """
                INSERT INTO knowledge (
                    key, value, category, confidence, source, access_count,
                    last_accessed_at, archived, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 0, NULL, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    confidence = excluded.confidence,
                    source = excluded.source,
                    archived = 0,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    normalized_key,
                    normalized_value,
                    normalized_category,
                    normalized_confidence,
                    normalized_source,
                ),
            )

    def get_knowledge(self, key: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM knowledge WHERE key = ? AND archived = 0",
                (key,),
            ).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE knowledge
                    SET access_count = access_count + 1,
                        last_accessed_at = CURRENT_TIMESTAMP
                    WHERE key = ?
                    """,
                    (key,),
                )
        return row["value"] if row else None

    def list_knowledge(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT key, value, updated_at, category, confidence, source
                FROM knowledge
                WHERE archived = 0
                ORDER BY confidence DESC, updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_knowledge(self, key: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM knowledge WHERE key = ?", (key,))
        return cursor.rowcount > 0

    def remember_episode(
        self,
        summary: str,
        details: str,
        *,
        tags: Iterable[str] | None = None,
        importance: float = 0.5,
        session_id: Optional[str] = None,
    ) -> int:
        serialized_tags = json.dumps(sorted(set(tags or [])), ensure_ascii=False)
        normalized_importance = _clamp(importance, 0.0, 1.0)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO episodes (session_id, summary, details, tags, importance)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, summary.strip(), details.strip(), serialized_tags, normalized_importance),
            )
            return int(cursor.lastrowid)

    def list_recent_episodes(self, limit: int = 10) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, summary, details, tags, importance, created_at, last_accessed_at
                FROM episodes
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        episodes = [dict(row) for row in rows]
        for episode in episodes:
            episode["tags"] = json.loads(episode["tags"] or "[]")
        return episodes

    def save_reflection(
        self,
        question: str,
        answer_summary: str,
        *,
        outcome: str,
        lessons: str,
        confidence: float = 0.7,
    ) -> int:
        normalized_confidence = _clamp(confidence, 0.0, 1.0)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO reflections (question, answer_summary, outcome, lessons, confidence)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    question.strip(),
                    answer_summary.strip(),
                    outcome.strip(),
                    lessons.strip(),
                    normalized_confidence,
                ),
            )
            return int(cursor.lastrowid)

    def list_recent_reflections(self, limit: int = 10, outcome: Optional[str] = None) -> list[dict]:
        query = """
            SELECT question, answer_summary, outcome, lessons, confidence, created_at
            FROM reflections
        """
        params: list[str | int] = []
        if outcome:
            query += " WHERE outcome = ?"
            params.append(outcome)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def set_goal(
        self,
        goal: str,
        *,
        success_criteria: str = "",
        priority: int = 3,
        status: str = "active",
    ) -> None:
        normalized_goal = goal.strip()
        normalized_status = status.strip() or "active"
        normalized_priority = max(1, min(priority, 5))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO goals (goal, status, priority, success_criteria, created_at, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(goal) DO UPDATE SET
                    status = excluded.status,
                    priority = excluded.priority,
                    success_criteria = excluded.success_criteria,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (normalized_goal, normalized_status, normalized_priority, success_criteria.strip()),
            )

    def update_goal_status(self, goal: str, status: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE goals
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE goal = ?
                """,
                (status.strip(), goal.strip()),
            )
        return cursor.rowcount > 0

    def list_goals(self, limit: int = 10, status: Optional[str] = "active") -> list[dict]:
        query = """
            SELECT goal, status, priority, success_criteria, created_at, updated_at
            FROM goals
        """
        params: list[str | int] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY priority ASC, updated_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def search_relevant_memories(self, query: str, limit: int = 8) -> list[dict]:
        tokens = _tokenize(query)
        if not tokens:
            return []

        candidates: list[dict] = []
        with self._connect() as conn:
            knowledge_rows = conn.execute(
                """
                SELECT key, value, updated_at, confidence, category
                FROM knowledge
                WHERE archived = 0
                ORDER BY updated_at DESC
                LIMIT 100
                """
            ).fetchall()
            for row in knowledge_rows:
                text = f"{row['key']} {row['value']} {row['category']}"
                overlap = len(tokens & _tokenize(text))
                if overlap == 0:
                    continue
                candidates.append(
                    {
                        "memory_type": "knowledge",
                        "score": overlap * 2.5 + float(row["confidence"] or 0),
                        "text": f"{row['key']}: {row['value']}",
                        "timestamp": row["updated_at"],
                    }
                )

            conversation_rows = conn.execute(
                """
                SELECT role, content, timestamp
                FROM conversations
                ORDER BY timestamp DESC, id DESC
                LIMIT 120
                """
            ).fetchall()
            for row in conversation_rows:
                overlap = len(tokens & _tokenize(row["content"]))
                if overlap == 0:
                    continue
                role_label = "用户" if row["role"] == "user" else "我"
                candidates.append(
                    {
                        "memory_type": "conversation",
                        "score": overlap * 1.5,
                        "text": f"{role_label}: {row['content'][:220]}",
                        "timestamp": row["timestamp"],
                    }
                )

            episode_rows = conn.execute(
                """
                SELECT summary, details, tags, importance, created_at
                FROM episodes
                ORDER BY created_at DESC
                LIMIT 80
                """
            ).fetchall()
            for row in episode_rows:
                tags = " ".join(json.loads(row["tags"] or "[]"))
                searchable_text = f"{row['summary']} {row['details']} {tags}"
                overlap = len(tokens & _tokenize(searchable_text))
                if overlap == 0:
                    continue
                candidates.append(
                    {
                        "memory_type": "episode",
                        "score": overlap * 2 + float(row["importance"] or 0),
                        "text": f"{row['summary']} — {row['details'][:180]}",
                        "timestamp": row["created_at"],
                    }
                )

            reflection_rows = conn.execute(
                """
                SELECT question, answer_summary, outcome, lessons, confidence, created_at
                FROM reflections
                ORDER BY created_at DESC
                LIMIT 60
                """
            ).fetchall()
            for row in reflection_rows:
                searchable_text = f"{row['question']} {row['answer_summary']} {row['lessons']}"
                overlap = len(tokens & _tokenize(searchable_text))
                if overlap == 0:
                    continue
                candidates.append(
                    {
                        "memory_type": "reflection",
                        "score": overlap * 1.8 + float(row["confidence"] or 0),
                        "text": f"{row['outcome']}: {row['lessons'][:180]}",
                        "timestamp": row["created_at"],
                    }
                )

            goal_rows = conn.execute(
                """
                SELECT goal, success_criteria, priority, updated_at
                FROM goals
                WHERE status = 'active'
                ORDER BY priority ASC, updated_at DESC
                LIMIT 30
                """
            ).fetchall()
            for row in goal_rows:
                searchable_text = f"{row['goal']} {row['success_criteria']}"
                overlap = len(tokens & _tokenize(searchable_text))
                if overlap == 0:
                    continue
                priority = max(int(row["priority"] or 3), 1)
                candidates.append(
                    {
                        "memory_type": "goal",
                        "score": overlap * 2.2 + (6 - priority) * 0.3,
                        "text": f"{row['goal']}（完成标准：{row['success_criteria'] or '未设置'}）",
                        "timestamp": row["updated_at"],
                    }
                )

        candidates.sort(key=lambda item: (item["score"], item["timestamp"]), reverse=True)
        return candidates[:limit]

    def format_recent_context(self, limit: int = 5) -> str:
        conversations = self.get_recent_conversations(limit=limit)
        if not conversations:
            return ""

        lines = ["=== 最近对话 ==="]
        for conversation in conversations:
            role_label = "用户" if conversation["role"] == "user" else "我"
            lines.append(f"{role_label}: {conversation['content']}")
        lines.append("=" * 20)
        return "\n".join(lines)

    def format_context_for_question(
        self,
        question: str,
        *,
        recent_limit: int = 5,
        relevant_limit: int = 6,
        goal_limit: int = 3,
        reflection_limit: int = 3,
    ) -> str:
        sections: list[str] = []

        recent_context = self.format_recent_context(limit=recent_limit)
        if recent_context:
            sections.append(recent_context)

        active_goals = self.list_goals(limit=goal_limit, status="active")
        if active_goals:
            goal_lines = ["=== 当前目标 ==="]
            for goal in active_goals:
                criteria = goal["success_criteria"] or "未设置"
                goal_lines.append(f"- P{goal['priority']} {goal['goal']}（完成标准：{criteria}）")
            sections.append("\n".join(goal_lines))

        relevant_memories = self.search_relevant_memories(question, limit=relevant_limit)
        if relevant_memories:
            memory_lines = ["=== 相关记忆 ==="]
            for memory in relevant_memories:
                memory_lines.append(f"- [{memory['memory_type']}] {memory['text']}")
            sections.append("\n".join(memory_lines))

        reflections = self.list_recent_reflections(limit=reflection_limit, outcome="success")
        if reflections:
            reflection_lines = ["=== 最近有效经验 ==="]
            for reflection in reflections:
                reflection_lines.append(f"- {reflection['lessons'][:180]}")
            sections.append("\n".join(reflection_lines))

        return "\n\n".join(section for section in sections if section)


_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """获取全局记忆管理器实例。"""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
