#!/usr/bin/env python3
"""
main.py — Lobster 项目入口

功能：
  - 启动 Agent HTTP 服务（默认端口 8765），供前端调用
  - 作为常驻进程运行基于 SQLite 的动态调度器，无需依赖系统 crontab
  - 启动时自动加载内置任务和用户创建的动态任务

用法：
  python main.py            # 启动 Agent 服务 + 调度器
  python main.py --now all  # 立即执行全部任务（测试用）
  python main.py --now finance   # 立即执行财经简报
  python main.py --now food      # 立即执行餐饮趋势
  python main.py --now earnings  # 立即执行财报日历
"""

import sys
import logging
import argparse
import threading

from dotenv import load_dotenv
from service.db import get_task_record
from service.scheduler import initialize_scheduler, run_scheduler_loop, run_task_by_name
load_dotenv()

# ── 日志配置 ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("lobster.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("lobster")


def run_scheduler():
    """调度循环（在独立线程中运行）。"""
    tasks = initialize_scheduler()
    log.info("⏰ 调度器启动")
    for task in tasks:
        log.info("   %s: %s → %s", task["name"], task["schedule_expr"], task["notify_channel"])
    run_scheduler_loop()


# ── 入口 ──────────────────────────────────────────────────────────────────────

_BUILTIN_TASKS = ("finance", "food", "earnings")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lobster — 财经 & 餐饮日报调度器 + Agent 服务")
    parser.add_argument(
        "--now",
        metavar="TASK",
        help="立即执行指定任务：finance / food / earnings / all，或任意已存在任务名",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Agent HTTP 服务端口（默认 8765）",
    )
    args = parser.parse_args()

    if args.now:
        initialize_scheduler()
        if args.now == "all":
            task_names = list(_BUILTIN_TASKS)
        elif get_task_record(args.now):
            task_names = [args.now]
        else:
            print(f"未知任务 '{args.now}'，可选：finance / food / earnings / all，或任意已创建任务名")
            sys.exit(1)
        for task_name in task_names:
            print(run_task_by_name(task_name))
    else:
        log.info("🦞 Lobster 启动")

        # 调度器在后台线程运行
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()

        # Agent HTTP 服务在主线程运行
        from service.server import start_server
        try:
            start_server(port=args.port)
        except KeyboardInterrupt:
            log.info("🛑 已停止")
