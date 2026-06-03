import tempfile
import unittest
from pathlib import Path

from service.agent import LobsterBrain
from service.memory import MemoryManager


class LobsterBrainTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "brain-memory.db"
        self.memory = MemoryManager(db_path=self.db_path)
        self.brain = LobsterBrain(memory_manager=self.memory)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_prepare_injects_context_and_tracks_building_goal(self):
        self.memory.save_knowledge("frontend_contract", "前端问答接口返回 answer 文本字段")
        prepared = self.brain.prepare("请优化前端问答体验")

        self.assertEqual(prepared.intent, "building")
        self.assertIn("=== 当前认知框架 ===", prepared.prompt)
        self.assertIn("前端问答接口返回 answer 文本字段", prepared.prompt)
        self.assertIsNotNone(prepared.tracked_goal)
        self.assertEqual(self.memory.list_goals(limit=1, status="active")[0]["goal"], prepared.tracked_goal)

    def test_answer_persists_conversation_reflection_episode_and_goal_status(self):
        answer = self.brain.answer(
            "请优化长期任务调度",
            lambda prompt: f"已收到：{prompt.splitlines()[-1]}",
            session_id="test-session",
        )

        self.assertIn("当前问题：请优化长期任务调度", answer)

        conversations = self.memory.get_recent_conversations(limit=2, session_id="test-session")
        reflections = self.memory.list_recent_reflections(limit=1)
        episodes = self.memory.list_recent_episodes(limit=1)
        goals = self.memory.list_goals(limit=1, status="completed")

        self.assertEqual([item["role"] for item in conversations], ["user", "agent"])
        self.assertEqual(reflections[0]["outcome"], "success")
        self.assertIn("请优化长期任务调度", episodes[0]["summary"])
        self.assertEqual(goals[0]["status"], "completed")

    def test_answer_failure_marks_goal_blocked(self):
        with self.assertRaises(RuntimeError):
            self.brain.answer("请修复核心报错", lambda prompt: (_ for _ in ()).throw(RuntimeError("boom")))

        goals = self.memory.list_goals(limit=1, status="blocked")
        reflections = self.memory.list_recent_reflections(limit=1)

        self.assertEqual(goals[0]["status"], "blocked")
        self.assertEqual(reflections[0]["outcome"], "failure")


if __name__ == "__main__":
    unittest.main()
