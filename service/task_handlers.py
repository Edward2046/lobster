"""
service/task_handlers.py — 任务处理器

将任务执行逻辑从数据库代码中抽离出来，提供结构化的任务处理方式。

任务类型：
  - report: 报告生成任务（财经/餐饮/财报）
  - custom: 自定义代码任务
"""

import json
from typing import Any


def execute_report_task(params: dict, context: dict) -> str:
    """执行报告类任务（财经/餐饮/财报）

    Args:
        params: 任务参数，包含 report_type
        context: 执行上下文，包含 notify_channel, send_notification_result 等

    Returns:
        执行结果字符串
    """
    report_type = params.get("report_type")
    if not report_type:
        raise ValueError("Report task requires 'report_type' parameter")

    # 动态导入对应的报告模块
    if report_type == "finance":
        from service.reports.finance import build_report
    elif report_type == "food_trends":
        from service.reports.food_trends import build_report
    elif report_type == "earnings":
        from service.reports.earnings import build_report
    else:
        raise ValueError(f"Unknown report_type: {report_type}")

    title, content = build_report()
    notify_channel = context["notify_channel"]
    send_notification_result = context["send_notification_result"]

    notification = send_notification_result(notify_channel, title, content)
    if not notification["ok"]:
        raise RuntimeError(notification["message"])

    return f"{notification['message']}\n\n{title}\n\n{content}"


def execute_custom_task(params: dict, context: dict) -> str:
    """执行自定义代码任务

    Args:
        params: 任务参数，包含 code
        context: 执行上下文

    Returns:
        执行结果字符串
    """
    code = params.get("code")
    if not code:
        raise ValueError("Custom task requires 'code' parameter")

    from service.tools.code_executor_tool import execute_python_code

    outcome = execute_python_code(code, extra_globals=context.get("extra_globals", {}))

    if not outcome["success"]:
        raise RuntimeError(outcome["rendered"] or "Custom task execution failed")

    return outcome["rendered"] or "Custom task executed successfully."


# 任务处理器注册表
TASK_HANDLERS = {
    "report": execute_report_task,
    "custom": execute_custom_task,
}


def execute_task(task_type: str, params: dict, context: dict) -> str:
    """根据任务类型分发到对应的处理器

    Args:
        task_type: 任务类型（report / custom）
        params: 任务参数（从 task_params JSON 解析）
        context: 执行上下文

    Returns:
        执行结果字符串
    """
    handler = TASK_HANDLERS.get(task_type)
    if handler is None:
        raise ValueError(f"Unknown task_type: {task_type}. Valid types: {list(TASK_HANDLERS.keys())}")

    return handler(params, context)


def parse_task_params(task_params: str | None) -> dict:
    """解析任务参数 JSON 字符串"""
    if not task_params:
        return {}
    try:
        return json.loads(task_params)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid task_params JSON: {e}")


def serialize_task_params(params: dict) -> str:
    """序列化任务参数为 JSON 字符串"""
    return json.dumps(params, ensure_ascii=False)
