# task_manager_tool.py — 动态任务管理工具

import json
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
_ALLOWED_TASK_TYPES = {"report", "custom"}
_ALLOWED_REPORT_TYPES = {"finance", "food_trends", "earnings"}


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


def _validate_task_type(task_type: str) -> str:
    normalized = task_type.strip().lower()
    if normalized not in _ALLOWED_TASK_TYPES:
        raise ValueError(f"task_type must be one of: {', '.join(_ALLOWED_TASK_TYPES)}.")
    return normalized


def _validate_task_params(task_type: str, params: dict) -> dict:
    """根据任务类型校验参数"""
    if task_type == "report":
        report_type = params.get("report_type")
        if not report_type:
            raise ValueError("Report task requires 'report_type' in task_params.")
        if report_type not in _ALLOWED_REPORT_TYPES:
            raise ValueError(f"report_type must be one of: {', '.join(_ALLOWED_REPORT_TYPES)}.")
    elif task_type == "custom":
        if not params.get("code"):
            raise ValueError("Custom task requires 'code' in task_params.")
    return params


def _format_task(task: dict) -> str:
    enabled = "yes" if task.get("enabled") else "no"
    last_run_at = task.get("last_run_at") or "never"
    description = task.get("description") or "-"
    task_type = task.get("task_type") or "custom"
    params = task.get("task_params") or "{}"
    return (
        f"- `{task['name']}` — {task['schedule_expr']}\n"
        f"  - type: {task_type}\n"
        f"  - params: {params}\n"
        f"  - description: {description}\n"
        f"  - enabled: {enabled}\n"
        f"  - last_run_at: {last_run_at}"
    )


@tool
def create_task(
    name: str,
    schedule_expr: str,
    notify_channel: str,
    description: str,
    task_type: str = "custom",
    task_params: str = "{}",
) -> str:
    """Create a new dynamic task and register it with the scheduler.

    Args:
        name: Unique task name in slug format (lowercase letters, numbers, hyphens).
        schedule_expr: Natural-language schedule expression like 'every day at 09:00',
                       'every monday at 08:00', 'every 30 minutes', 'every hour'.
        notify_channel: 'wxpusher', 'feishu', or 'none'.
        description: Human-readable description of the task.
        task_type: Task type. 'report' for built-in reports (finance/food_trends/earnings),
                   or 'custom' for custom Python code. Defaults to 'custom'.
        task_params: JSON string of task parameters. For 'report' type:
                     '{"report_type": "finance"}' or "food_trends" or "earnings".
                     For 'custom' type: '{"code": "your python code here"}'.
    """
    initialize_scheduler()
    task_name = _validate_task_name(name)
    parsed_channel = _validate_notify_channel(notify_channel)
    parsed_type = _validate_task_type(task_type)
    parse_schedule_expr(schedule_expr)

    try:
        params_dict = json.loads(task_params) if isinstance(task_params, str) else task_params
    except json.JSONDecodeError as e:
        return f"Invalid task_params JSON: {e}"

    try:
        validated_params = _validate_task_params(parsed_type, params_dict)
    except ValueError as e:
        return str(e)

    try:
        task = create_task_record(
            name=task_name,
            schedule_expr=schedule_expr.strip(),
            task_type=parsed_type,
            task_params=validated_params,
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
    task_type: str | None = None,
    task_params: str | None = None,
    notify_channel: str | None = None,
    description: str | None = None,
) -> str:
    """Update a task's schedule, type, parameters, channel, or description.

    Args:
        name: Task name in slug format.
        schedule_expr: Optional updated schedule expression.
        task_type: Optional updated task type ('report' or 'custom').
        task_params: Optional updated JSON parameters string.
        notify_channel: Optional updated channel: 'wxpusher', 'feishu', or 'none'.
        description: Optional updated description.
    """
    initialize_scheduler()
    task_name = _validate_task_name(name)
    existing = get_task_record(task_name)
    if existing is None:
        return f"Task '{task_name}' not found."

    updates = {}
    if schedule_expr is not None:
        parse_schedule_expr(schedule_expr)
        updates["schedule_expr"] = schedule_expr.strip()
    if task_type is not None:
        updates["task_type"] = _validate_task_type(task_type)
    if task_params is not None:
        try:
            params_dict = json.loads(task_params) if isinstance(task_params, str) else task_params
        except json.JSONDecodeError as e:
            return f"Invalid task_params JSON: {e}"
        # 校验参数（结合当前或更新后的 task_type）
        effective_type = updates.get("task_type") or existing.get("task_type", "custom")
        try:
            updates["task_params"] = _validate_task_params(effective_type, params_dict)
        except ValueError as e:
            return str(e)
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
