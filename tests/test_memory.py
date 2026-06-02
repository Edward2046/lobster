import sqlite3
import tempfile
import unittest
from pathlib import Path

from service.memory import MemoryManager


class MemoryManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "memory.db"
        self.memory = MemoryManager(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_knowledge_tracks_revisions_and_metadata(self):
        self.memory.save_knowledge("user_language", "中文", source="user")
        self.memory.save_knowledge("user_language", "英文", source="user")

        self.assertEqual(self.memory.get_knowledge("user_language"), "英文")

        with sqlite3.connect(self.db_path) as conn:
            revision = conn.execute(
                "SELECT old_value, new_value, source FROM knowledge_revisions WHERE key = ?",
                ("user_language",),
            ).fetchone()
            access_count = conn.execute(
                "SELECT access_count FROM knowledge WHERE key = ?",
                ("user_language",),
            ).fetchone()[0]

        self.assertEqual(revision, ("中文", "英文", "user"))
        self.assertEqual(access_count, 1)

    def test_context_builder_includes_goals_and_relevant_memories(self):
        self.memory.save_conversation("user", "帮我优化餐饮日报")
        self.memory.save_conversation("agent", "先看现有调度结构。")
        self.memory.save_knowledge("product_focus", "餐饮日报自动化", category="semantic")
        self.memory.set_goal("优化日报生成链路", success_criteria="输出更稳定", priority=1)
        self.memory.save_reflection(
            "如何优化日报？",
            "先梳理流程",
            outcome="success",
            lessons="复杂优化任务要先整理目标和上下文。",
        )

        context = self.memory.format_context_for_question("继续优化餐饮日报")

        self.assertIn("=== 当前目标 ===", context)
        self.assertIn("优化日报生成链路", context)
        self.assertIn("餐饮日报自动化", context)
        self.assertIn("复杂优化任务要先整理目标和上下文", context)

    def test_episode_and_reflection_listing_preserves_structure(self):
        self.memory.remember_episode(
            "修复定时任务异常",
            "补齐任务依赖并验证执行结果。",
            tags=["automation", "success"],
            importance=0.9,
        )
        self.memory.save_reflection(
            "为什么任务失败？",
            "缺少依赖",
            outcome="success",
            lessons="先检查依赖声明。",
            confidence=0.8,
        )

        episodes = self.memory.list_recent_episodes(limit=1)
        reflections = self.memory.list_recent_reflections(limit=1)

        self.assertEqual(episodes[0]["tags"], ["automation", "success"])
        self.assertEqual(reflections[0]["lessons"], "先检查依赖声明。")


if __name__ == "__main__":
    unittest.main()
