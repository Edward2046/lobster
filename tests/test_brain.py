import tempfile
import unittest
from pathlib import Path

import ast

from service.agent import LobsterBrain
from service.agent.brain import _extract_text_from_parse_error, sanitize_agent_code
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

    def test_extract_text_from_parse_error_strips_smolagents_guidance(self):
        exc = RuntimeError(
            'Error in code parsing: Your code snippet is invalid, because the regex pattern '
            '<code>(.*?)</code> was not found in it. Here is your code snippet: '
            '我已经准备好接收您的阿里云登录Cookie。请您按照上面的指引，将Cookie粘贴给我，我会用它对阿里云SLS页面进行模拟登录，'
            '从而帮您查看和筛选日志内容。</code> Make sure to include code with the correct pattern, '
            'for instance: Thoughts: Your thoughts <code> # Your python code here </code> '
            'Make sure to provide correct code blobs.'
        )

        recovered = _extract_text_from_parse_error(exc)

        self.assertEqual(
            recovered,
            "我已经准备好接收您的阿里云登录Cookie。请您按照上面的指引，将Cookie粘贴给我，我会用它对阿里云SLS页面进行模拟登录，从而帮您查看和筛选日志内容。",
        )

    def test_answer_recovers_plain_text_from_parse_error(self):
        parse_error = RuntimeError(
            'Error in code parsing: Your code snippet is invalid, because the regex pattern '
            '<code>(.*?)</code> was not found in it. Here is your code snippet: '
            '我已经准备好接收您的阿里云登录Cookie。</code> Make sure to include code with the correct pattern.'
        )

        answer = self.brain.answer("请帮我看 SLS 日志", lambda prompt: (_ for _ in ()).throw(parse_error))

        self.assertEqual(answer, "我已经准备好接收您的阿里云登录Cookie。")

    def test_sanitize_fixes_unterminated_multiline_final_answer(self):
        broken = (
            'final_answer("是的，您说得对。那个飞书知识库链接'
            '（`https://hypergryph.feishu.cn/wiki/Wv0SwWClNiUSPGkkI1McPEv5nEc`）的情况是这样的：\n'
            "- 第一点\n"
            '- 第二点")'
        )
        with self.assertRaises(SyntaxError):
            ast.parse(broken)

        fixed = sanitize_agent_code(broken)

        parsed = ast.parse(fixed)
        call = parsed.body[0].value
        self.assertEqual(call.func.id, "final_answer")
        self.assertIn("飞书知识库链接", call.args[0].value)
        self.assertIn("\n- 第一点", call.args[0].value)

    def test_sanitize_leaves_valid_code_untouched(self):
        valid = 'final_answer("已完成")'
        self.assertEqual(sanitize_agent_code(valid), valid)

        multi = "x = get_weather('北京')\nfinal_answer(x)"
        self.assertEqual(sanitize_agent_code(multi), multi)

    def test_sanitize_injects_missing_stdlib_import(self):
        code = 'task_params = {"a": 1}\nfinal_answer(json.dumps(task_params))'
        fixed = sanitize_agent_code(code)

        self.assertIn("import json", fixed)
        # 补的 import 要在最前面，且整体可解析
        self.assertTrue(fixed.startswith("import json"))
        ast.parse(fixed)

    def test_sanitize_injects_multiple_missing_imports(self):
        code = "final_answer(re.sub(r'x', 'y', datetime.datetime.now().isoformat()))"
        fixed = sanitize_agent_code(code)

        self.assertIn("import datetime", fixed)
        self.assertIn("import re", fixed)

    def test_sanitize_skips_already_imported_or_bound_names(self):
        already = 'import json\nfinal_answer(json.dumps({"a": 1}))'
        self.assertEqual(sanitize_agent_code(already), already)

        # json 被当成局部变量赋值，不应误补 import
        shadowed = 'json = {"a": 1}\nfinal_answer(json.get("a"))'
        self.assertEqual(sanitize_agent_code(shadowed), shadowed)

    def test_sanitize_ignores_non_whitelisted_modules(self):
        code = "final_answer(np.array([1, 2]).sum())"
        self.assertEqual(sanitize_agent_code(code), code)

    def test_sanitize_gives_up_on_unfixable_code(self):
        # 不是单一 final_answer 调用的坏代码，无法安全修复，应原样返回。
        broken = 'x = "开头没结尾\nfinal_answer(x)'
        self.assertEqual(sanitize_agent_code(broken), broken)

    def test_answer_stream_recovers_plain_text_from_parse_error(self):
        parse_error = RuntimeError(
            'Error in code parsing: Your code snippet is invalid, because the regex pattern '
            '<code>(.*?)</code> was not found in it. Here is your code snippet: '
            '请把 Cookie 发给我。</code> Make sure to include code with the correct pattern.'
        )

        def broken_stream_runner(prompt):
            raise parse_error
            yield

        events = list(self.brain.answer_stream("请帮我筛选日志", broken_stream_runner))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "final")
        self.assertEqual(events[0].text, "请把 Cookie 发给我。")


if __name__ == "__main__":
    unittest.main()
