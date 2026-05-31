import logging
import re
import threading
import time
from datetime import datetime, timezone

import schedule

from service.db import (
    create_builtin_task_if_missing,
    get_task_record,
    init_db,
    list_task_records,
    update_task_run_status,
)

log = logging.getLogger("lobster.scheduler")

scheduler = schedule.Scheduler()
_scheduler_lock = threading.RLock()

_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

_BUILTIN_TASKS = [
    {
        "name": "finance",
        "schedule_expr": "every day at 09:00",
        "notify_channel": "wxpusher",
        "description": "每天 09:00 推送财经简报",
        "code": """
from service.cron.daily_finance import build_report

title, content = build_report()
notify_result = send_notification(notify_channel, title, content)
if "failed" in notify_result.lower():
    raise RuntimeError(notify_result)
_result = f"{notify_result}\\n\\n{title}\\n\\n{content}"
""".strip(),
    },
    {
        "name": "food",
        "schedule_expr": "every day at 09:30",
        "notify_channel": "feishu",
        "description": "每天 09:30 推送餐饮趋势简报",
        "code": """
from service.cron.daily_food_trends import build_report

title, content = build_report()
notify_result = send_notification(notify_channel, title, content)
if "failed" in notify_result.lower():
    raise RuntimeError(notify_result)
_result = f"{notify_result}\\n\\n{title}\\n\\n{content}"
""".strip(),
    },
    {
        "name": "earnings",
        "schedule_expr": "every monday at 08:00",
        "notify_channel": "wxpusher",
        "description": "每周一 08:00 推送一周财报日历",
        "code": """
from service.cron.weekly_earnings import build_report

title, content = build_report()
notify_result = send_notification(notify_channel, title, content)
if "failed" in notify_result.lower():
    raise RuntimeError(notify_result)
_result = f"{notify_result}\\n\\n{title}\\n\\n{content}"
""".strip(),
    },
]


def parse_schedule_expr(schedule_expr: str) -> tuple[str, str | int]:
    expr = " ".join(schedule_expr.strip().lower().split())

    match = re.fullmatch(r"every day at (\d{2}:\d{2})", expr)
    if match:
        time.strptime(match.group(1), "%H:%M")
        return ("daily", match.group(1))

    match = re.fullmatch(rf"every ({'|'.join(_WEEKDAYS)}) at (\d{{2}}:\d{{2}})", expr)
    if match:
        time.strptime(match.group(2), "%H:%M")
        return (match.group(1), match.group(2))

    match = re.fullmatch(r"every (\d+) minutes?", expr)
    if match:
        minutes = int(match.group(1))
        if minutes <= 0:
            raise ValueError("Minute interval must be greater than 0.")
        return ("minutes", minutes)

    if expr == "every hour":
        return ("hourly", 1)

    raise ValueError(
        "Unsupported schedule expression. Use forms like "
        "'every day at 09:00', 'every monday at 08:00', "
        "'every 30 minutes', or 'every hour'."
    )


def ensure_builtin_tasks() -> None:
    for task in _BUILTIN_TASKS:
        create_builtin_task_if_missing(**task)


def register_task(task: dict) -> schedule.Job | None:
    with _scheduler_lock:
        scheduler.clear(task["name"])
        if not task.get("enabled", 1):
            return None

        kind, value = parse_schedule_expr(task["schedule_expr"])
        if kind == "daily":
            job = scheduler.every().day.at(value).do(run_task_by_name, task["name"])
        elif kind in _WEEKDAYS:
            job = getattr(scheduler.every(), kind).at(value).do(run_task_by_name, task["name"])
        elif kind == "minutes":
            job = scheduler.every(value).minutes.do(run_task_by_name, task["name"])
        else:
            job = scheduler.every().hour.do(run_task_by_name, task["name"])
        job.tag(task["name"])
        return job


def unregister_task(name: str) -> None:
    with _scheduler_lock:
        scheduler.clear(name)


def reload_scheduled_tasks() -> list[dict]:
    init_db()
    ensure_builtin_tasks()
    tasks = list_task_records(enabled_only=True)
    with _scheduler_lock:
        scheduler.clear()
        for task in tasks:
            register_task(task)
    return tasks


def initialize_scheduler() -> list[dict]:
    return reload_scheduled_tasks()


def run_task_by_name(name: str) -> str:
    task = get_task_record(name)
    if task is None:
        raise ValueError(f"Task '{name}' not found.")

    from service.tools.code_executor_tool import execute_python_code
    from service.tools.notify_tool import send_notification

    log.info("▶ 执行任务: %s", name)
    outcome = execute_python_code(
        task["code"],
        extra_globals={
            "send_notification": send_notification,
            "notify_channel": task["notify_channel"],
            "task_name": task["name"],
        },
    )

    timestamp = datetime.now(timezone.utc).isoformat()
    status = "success" if outcome["success"] else "error"
    update_task_run_status(name, last_run_at=timestamp, last_run_status=status)

    rendered = outcome["rendered"]
    if outcome["success"]:
        log.info("✅ 任务执行成功: %s", name)
        return rendered or f"Task '{name}' executed successfully."

    log.error("❌ 任务执行失败: %s", name)
    return rendered or f"Task '{name}' failed."


def run_scheduler_loop(sleep_seconds: int = 30) -> None:
    while True:
        with _scheduler_lock:
            scheduler.run_pending()
        time.sleep(sleep_seconds)
