"""
memory.py — Agent 记忆管理模块

提供三层记忆：
  1. 短期记忆：最近 N 条对话，自动注入到每次请求
  2. 长期记忆：完整对话历史，可通过工具检索
  3. 知识库：用户明确要求记住的事实/偏好

存储：SQLite 数据库（memory.db）
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

# 数据库路径
DB_PATH = Path(__file__).parent.parent / "memory.db"


class MemoryManager:
    """记忆管理器，负责对话历史和知识库的存储与检索。"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库表结构。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 对话历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 知识库表（用户要求记住的事实）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_timestamp
            ON conversations(timestamp DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_session
            ON conversations(session_id, timestamp DESC)
        """)

        conn.commit()
        conn.close()

    def save_conversation(
        self,
        role: str,
        content: str,
        session_id: Optional[str] = None
    ):
        """保存一条对话记录。

        Args:
            role: 'user' 或 'agent'
            content: 对话内容
            session_id: 会话 ID（可选，用于区分不同会话）
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        conn.commit()
        conn.close()

    def get_recent_conversations(
        self,
        limit: int = 10,
        session_id: Optional[str] = None
    ) -> list[dict]:
        """获取最近的对话记录。

        Args:
            limit: 返回条数
            session_id: 如果指定，只返回该会话的记录

        Returns:
            对话记录列表，每条包含 role, content, timestamp
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if session_id:
            cursor.execute("""
                SELECT role, content, timestamp
                FROM conversations
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (session_id, limit))
        else:
            cursor.execute("""
                SELECT role, content, timestamp
                FROM conversations
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        # 反转顺序，让最早的在前面
        return [dict(row) for row in reversed(rows)]

    def search_conversations(
        self,
        keyword: str,
        limit: int = 20,
        session_id: Optional[str] = None
    ) -> list[dict]:
        """搜索包含关键词的历史对话。

        Args:
            keyword: 搜索关键词
            limit: 返回条数
            session_id: 如果指定，只搜索该会话

        Returns:
            匹配的对话记录列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        search_pattern = f"%{keyword}%"
        if session_id:
            cursor.execute("""
                SELECT role, content, timestamp
                FROM conversations
                WHERE session_id = ? AND content LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (session_id, search_pattern, limit))
        else:
            cursor.execute("""
                SELECT role, content, timestamp
                FROM conversations
                WHERE content LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (search_pattern, limit))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def save_knowledge(self, key: str, value: str):
        """保存或更新知识库条目。

        Args:
            key: 知识点的键（如 "用户偏好_语言"）
            value: 知识点的值
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO knowledge (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (key, value))
        conn.commit()
        conn.close()

    def get_knowledge(self, key: str) -> Optional[str]:
        """获取知识库条目。

        Args:
            key: 知识点的键

        Returns:
            知识点的值，不存在返回 None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM knowledge WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def list_knowledge(self, limit: int = 50) -> list[dict]:
        """列出所有知识库条目。

        Args:
            limit: 返回条数

        Returns:
            知识点列表，每条包含 key, value, updated_at
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT key, value, updated_at
            FROM knowledge
            ORDER BY updated_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def delete_knowledge(self, key: str) -> bool:
        """删除知识库条目。

        Args:
            key: 知识点的键

        Returns:
            True 表示删除成功，False 表示不存在
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM knowledge WHERE key = ?", (key,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def format_recent_context(self, limit: int = 5) -> str:
        """格式化最近对话为上下文字符串，用于注入到 Agent。

        Args:
            limit: 包含最近几条对话

        Returns:
            格式化的上下文字符串
        """
        conversations = self.get_recent_conversations(limit=limit)
        if not conversations:
            return ""

        lines = ["=== 最近对话 ==="]
        for conv in conversations:
            role_label = "用户" if conv["role"] == "user" else "我"
            lines.append(f"{role_label}: {conv['content']}")
        lines.append("=" * 20)
        return "\n".join(lines)


# 全局单例
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """获取全局记忆管理器实例。"""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
