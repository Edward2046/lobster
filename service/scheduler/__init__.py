"""任务调度子系统。

包含：
- scheduler.core：调度循环、任务注册/反注册
- scheduler.handlers：按 task_type 分发的执行器
- scheduler.db：任务持久化
"""

from service.scheduler.core import (
    initialize_scheduler,
    parse_schedule_expr,
    register_task,
    reload_scheduled_tasks,
    run_scheduler_loop,
    run_task_by_name,
    scheduler,
    unregister_task,
)
from service.scheduler.db import (
    create_builtin_task_if_missing,
    create_task_record,
    delete_task_record,
    get_task_record,
    init_db,
    list_task_records,
    update_task_record,
    update_task_run_status,
)
from service.scheduler.handlers import (
    execute_task,
    parse_task_params,
    serialize_task_params,
)

__all__ = [
    # core
    "initialize_scheduler",
    "parse_schedule_expr",
    "register_task",
    "reload_scheduled_tasks",
    "run_scheduler_loop",
    "run_task_by_name",
    "scheduler",
    "unregister_task",
    # db
    "create_builtin_task_if_missing",
    "create_task_record",
    "delete_task_record",
    "get_task_record",
    "init_db",
    "list_task_records",
    "update_task_record",
    "update_task_run_status",
    # handlers
    "execute_task",
    "parse_task_params",
    "serialize_task_params",
]
