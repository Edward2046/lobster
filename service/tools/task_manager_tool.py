# task_manager_tool.py — 动态任务管理工具

import re
import sqlite3

from smolagents import tool

from service.db import (
    create_task_record,
    delete_task_record,
    get_task_record,
    list_task_records,
    update_task_record,
)
from service.scheduler import initialize_scheduler, parse_schedule_expr, register_task, run_task_by_name, unregister_task

_TASK_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ALLOWED_CHANNELS = {"wxpusher", "feishu", "none"}


def _validate_task_name(name: str) -> str:
    task_name = name.strip().lower()
    if not _TASK_NAME_RE.fullmatch(task_name):
        raise ValueError("Task name must be a slug using lowercase letters, numbers, and hyphens.")
    return task_name


def _validate_notify_channel(channel: str) -> str:
    notify_channel = channel.strip().lower()
    if notify_channel not in _ALLOWED_CHANNELS:
        raise ValueError("notify_channel must be one of: wxpusher, feishu, none.")
    return notify_channel


def _format_task(task: dict) -> str:
    enabled = "yes" if task.get("enabled") else "no"
    last_run_at = task.get("last_run_at") or "never"
    description = task.get("description") or "-"
    return (
        f"- `{task['name']}` — {task['schedule_expr']}\n"
        f"  - description: {description}\n"
        f"  - enabled: {enabled}\n"
        f"  - last_run_at: {last_run_at}"
    )


@tool
def create_task(name: str, schedule_expr: str, code: str, notify_channel: str, description: str) -> str:
    """Create a new dynamic task and register it with the scheduler.

    Args:
        name: Unique task name in slug format.
        schedule_expr: Natural-language schedule expression.
        code: Python code string to execute for the task.
        notify_channel: 'wxpusher', 'feishu', or 'none'.
        description: Human-readable description of the task.
    """
    initialize_scheduler()
    task_name = _validate_task_name(name)
    parsed_channel = _validate_notify_channel(notify_channel)
    parse_schedule_expr(schedule_expr)

    try:
        task = create_task_record(
            name=task_name,
            schedule_expr=schedule_expr.strip(),
            code=code,
            notify_channel=parsed_channel,
            description=description.strip(),
        )
    except sqlite3.IntegrityError:
        return f"Task '{task_name}' already exists."
    job = register_task(task)
    next_run = getattr(job, "next_run", None)
    return f"Task '{task_name}' created successfully. Next run: {next_run or 'when scheduler starts'}."


@tool
def list_tasks() -> str:
    """List all dynamic and builtin tasks."""
    initialize_scheduler()
    tasks = list_task_records()
    if not tasks:
        return "No tasks found."
    return "\n\n".join(_format_task(task) for task in tasks)


@tool
def delete_task(name: str) -> str:
    """Delete a task from the database and scheduler.

    Args:
        name: Task name in slug format.
    """
    initialize_scheduler()
    task_name = _validate_task_name(name)
    unregister_task(task_name)
    if not delete_task_record(task_name):
        return f"Task '{task_name}' not found."
    return f"Task '{task_name}' deleted successfully."


@tool
def run_task_now(name: str) -> str:
    """Run a task immediately without changing its schedule.

    Args:
        name: Task name in slug format.
    """
    initialize_scheduler()
    task_name = _validate_task_name(name)
    return run_task_by_name(task_name)


@tool
def update_task(
    name: str,
    schedule_expr: str | None = None,
    code: str | None = None,
    notify_channel: str | None = None,
    description: str | None = None,
) -> str:
    """Update a task's schedule, code, notification channel, or description.

    Args:
        name: Task name in slug format.
        schedule_expr: Optional updated schedule expression.
        code: Optional updated Python code.
        notify_channel: Optional updated channel: 'wxpusher', 'feishu', or 'none'.
        description: Optional updated description.
    """
    initialize_scheduler()
    task_name = _validate_task_name(name)
    if get_task_record(task_name) is None:
        return f"Task '{task_name}' not found."

    updates = {}
    if schedule_expr is not None:
        parse_schedule_expr(schedule_expr)
        updates["schedule_expr"] = schedule_expr.strip()
    if code is not None:
        updates["code"] = code
    if notify_channel is not None:
        updates["notify_channel"] = _validate_notify_channel(notify_channel)
    if description is not None:
        updates["description"] = description.strip()

    task = update_task_record(task_name, **updates)
    if task is None:
        return f"Task '{task_name}' not found."
    job = register_task(task)
    next_run = getattr(job, "next_run", None)
    return f"Task '{task_name}' updated successfully. Next run: {next_run or 'when scheduler starts'}."
