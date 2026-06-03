import os
import tempfile
import unittest
from unittest.mock import patch

from service.scheduler import (
    get_task_record,
    initialize_scheduler,
    list_task_records,
    parse_schedule_expr,
    scheduler,
)
from service.tools.task_manager_tool import create_task, delete_task, list_tasks, run_task_now, update_task


class DynamicTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["LOBSTER_TASK_DB"] = os.path.join(self.temp_dir.name, "tasks.db")
        scheduler.clear()

    def tearDown(self):
        scheduler.clear()
        os.environ.pop("LOBSTER_TASK_DB", None)
        self.temp_dir.cleanup()

    def test_initialize_scheduler_seeds_builtin_tasks(self):
        tasks = initialize_scheduler()
        builtin_names = {task["name"] for task in tasks if task["builtin"]}
        self.assertEqual(builtin_names, {"finance", "food", "earnings", "tech_news"})

    def test_parse_schedule_expr_supports_required_formats(self):
        self.assertEqual(parse_schedule_expr("every day at 09:00"), ("daily", "09:00"))
        self.assertEqual(parse_schedule_expr("every monday at 08:00"), ("monday", "08:00"))
        self.assertEqual(parse_schedule_expr("every 30 minutes"), ("minutes", 30))
        self.assertEqual(parse_schedule_expr("every hour"), ("hourly", 1))

    def test_task_lifecycle(self):
        create_task(
            name="demo-task",
            schedule_expr="every 30 minutes",
            notify_channel="none",
            description="demo task",
            task_type="custom",
            task_params='{"code": "print(\\"hello from task\\")\\n_result = 42"}',
        )

        rendered_list = list_tasks()
        self.assertIn("demo-task", rendered_list)
        self.assertIn("every 30 minutes", rendered_list)

        update_task("demo-task", schedule_expr="every hour", description="updated task")
        rendered_list = list_tasks()
        self.assertIn("every hour", rendered_list)
        self.assertIn("updated task", rendered_list)

        output = run_task_now("demo-task")
        self.assertIn("hello from task", output)
        self.assertIn("42", output)

        task = get_task_record("demo-task")
        self.assertEqual(task["last_run_status"], "success")
        self.assertIsNotNone(task["last_run_at"])

        delete_task("demo-task")
        remaining_names = {task["name"] for task in list_task_records()}
        self.assertNotIn("demo-task", remaining_names)

    def test_run_task_injects_tool_globals(self):
        create_task(
            name="tool-task",
            schedule_expr="every hour",
            notify_channel="feishu",
            description="tool globals",
            task_type="custom",
            task_params='{"code": "_result = search_web(\\"latest ai news\\")"}',
        )

        with patch(
            "service.tools.code_executor_tool.execute_python_code",
            return_value={"success": True, "rendered": "ok"},
        ) as mock_execute:
            output = run_task_now("tool-task")

        self.assertEqual(output, "ok")
        extra_globals = mock_execute.call_args.kwargs["extra_globals"]
        self.assertIn("get_current_time", extra_globals)
        self.assertIn("calculate", extra_globals)
        self.assertIn("get_weather", extra_globals)
        self.assertIn("get_investing_news", extra_globals)
        self.assertIn("get_earnings_calendar", extra_globals)
        self.assertIn("get_food_trends", extra_globals)
        self.assertIn("search_web", extra_globals)
        self.assertEqual(extra_globals["notify_channel"], "feishu")
        self.assertEqual(extra_globals["task_name"], "tool-task")


if __name__ == "__main__":
    unittest.main()
