import os
import tempfile
import unittest

from service.db import get_task_record, list_task_records
from service.scheduler import initialize_scheduler, parse_schedule_expr, scheduler
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
        self.assertEqual(builtin_names, {"finance", "food", "earnings"})

    def test_parse_schedule_expr_supports_required_formats(self):
        self.assertEqual(parse_schedule_expr("every day at 09:00"), ("daily", "09:00"))
        self.assertEqual(parse_schedule_expr("every monday at 08:00"), ("monday", "08:00"))
        self.assertEqual(parse_schedule_expr("every 30 minutes"), ("minutes", 30))
        self.assertEqual(parse_schedule_expr("every hour"), ("hourly", 1))

    def test_task_lifecycle(self):
        create_task(
            "demo-task",
            "every 30 minutes",
            "print('hello from task')\n_result = 42",
            "none",
            "demo task",
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


if __name__ == "__main__":
    unittest.main()
