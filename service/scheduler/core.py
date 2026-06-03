import logging
import re
import threading
import time
from datetime import datetime, timezone

import schedule

from service.scheduler.db import (
    create_builtin_task_if_missing,
    get_task_record,
    init_db,
    list_task_records,
    update_task_run_status,
)
from service.scheduler.handlers import execute_task, parse_task_params

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

# 内置任务定义（结构化方式，无需手写代码）
_BUILTIN_TASKS = [
    {
        "name": "finance",
        "schedule_expr": "every day at 09:00",
        "notify_channel": "wxpusher",
        "description": "每天 09:00 推送财经简报",
        "task_type": "report",
        "task_params": {"report_type": "finance"},
    },
    {
        "name": "food",
        "schedule_expr": "every day at 09:30",
        "notify_channel": "wxpusher",
        "description": "每天 09:30 推送餐饮趋势简报",
        "task_type": "report",
        "task_params": {"report_type": "food_trends", "markdown": True},
    },
    {
        "name": "earnings",
        "schedule_expr": "every monday at 08:00",
        "notify_channel": "wxpusher",
        "description": "每周一 08:00 推送一周财报日历",
        "task_type": "report",
        "task_params": {"report_type": "earnings"},
    },
    {
        "name": "tech_news",
        "schedule_expr": "every day at 09:00",
        "notify_channel": "wxpusher",
        "description": "每天 09:00 聚合科技资讯并由 LLM 提炼影响美股的重磅信息",
        "task_type": "report",
        "task_params": {"report_type": "tech_news", "markdown": True},
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


def _build_execution_context(task: dict) -> dict:
    """构建任务执行上下文（包含工具和通知函数）"""
    from service.tools.notify_tool import send_notification, send_notification_result
    from service.tools import (
        calculate,
        get_current_time,
        get_earnings_calendar,
        get_food_trends,
        get_investing_news,
        get_weather,
        search_web,
    )

    tool_globals = {
        "get_current_time": get_current_time,
        "calculate": calculate,
        "get_weather": get_weather,
        "get_investing_news": get_investing_news,
        "get_earnings_calendar": get_earnings_calendar,
        "get_food_trends": get_food_trends,
        "search_web": search_web,
        "send_notification": send_notification,
        "send_notification_result": send_notification_result,
        "notify_channel": task["notify_channel"],
        "task_name": task["name"],
    }

    return {
        "notify_channel": task["notify_channel"],
        "task_name": task["name"],
        "send_notification": send_notification,
        "send_notification_result": send_notification_result,
        "extra_globals": tool_globals,
    }


def run_task_by_name(name: str) -> str:
    task = get_task_record(name)
    if task is None:
        raise ValueError(f"Task '{name}' not found.")

    log.info("▶ 执行任务: %s (类型: %s)", name, task.get("task_type", "custom"))

    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        # 解析任务参数
        params = parse_task_params(task.get("task_params"))

        # 构建执行上下文
        context = _build_execution_context(task)

        # 通过任务处理器执行
        result = execute_task(
            task_type=task.get("task_type", "custom"),
            params=params,
            context=context,
        )

        update_task_run_status(name, last_run_at=timestamp, last_run_status="success")
        log.info("✅ 任务执行成功: %s", name)
        return result or f"Task '{name}' executed successfully."

    except Exception as e:
        update_task_run_status(name, last_run_at=timestamp, last_run_status="error")
        log.error("❌ 任务执行失败: %s, 错误: %s", name, e)
        return f"Task '{name}' failed: {e}"


def run_scheduler_loop(sleep_seconds: int = 30) -> None:
    while True:
        with _scheduler_lock:
            scheduler.run_pending()
        time.sleep(sleep_seconds)
