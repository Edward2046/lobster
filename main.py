#!/usr/bin/env python3
"""
main.py — Lobster 项目入口

功能：
  - 启动 Agent HTTP 服务（默认端口 8765），供前端调用
  - 作为常驻进程运行内置调度器，无需依赖系统 crontab
  - 每天 09:00 推送财经简报（WxPusher）
  - 每天 09:30 推送餐饮趋势简报（飞书）
  - 每周一 08:00 推送一周财报日历（WxPusher）

用法：
  python main.py            # 启动 Agent 服务 + 调度器
  python main.py --now all  # 立即执行全部任务（测试用）
  python main.py --now finance   # 立即执行财经简报
  python main.py --now food      # 立即执行餐饮趋势
  python main.py --now earnings  # 立即执行财报日历
"""

import sys
import time
import logging
import argparse
import threading
from datetime import datetime

from dotenv import load_dotenv
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


# ── 任务函数 ──────────────────────────────────────────────────────────────────

def run_finance():
    """每天 09:00 — 财经简报 → WxPusher"""
    from service.cron.daily_finance import build_report
    from service.cron.notify import send_wxpusher
    log.info("▶ 开始生成财经简报...")
    try:
        title, content = build_report()
        ok = send_wxpusher(title, content)
        log.info("✅ 财经简报推送%s", "成功" if ok else "失败")
    except Exception as e:
        log.error("❌ 财经简报异常: %s", e)


def run_food():
    """每天 09:30 — 餐饮趋势简报 → 飞书"""
    from service.cron.daily_food_trends import build_report
    from service.cron.notify import send_feishu
    log.info("▶ 开始生成餐饮趋势简报...")
    try:
        title, content = build_report()
        ok = send_feishu(title, content)
        log.info("✅ 餐饮趋势简报推送%s", "成功" if ok else "失败")
    except Exception as e:
        log.error("❌ 餐饮趋势简报异常: %s", e)


def run_earnings():
    """每周一 08:00 — 财报日历 → WxPusher"""
    from service.cron.weekly_earnings import build_report
    from service.cron.notify import send_wxpusher
    log.info("▶ 开始生成财报日历...")
    try:
        title, content = build_report()
        ok = send_wxpusher(title, content)
        log.info("✅ 财报日历推送%s", "成功" if ok else "失败")
    except Exception as e:
        log.error("❌ 财报日历异常: %s", e)


# ── 调度器 ────────────────────────────────────────────────────────────────────

_executed_today: set[str] = set()
_last_date: str = ""


def _check_and_run():
    """每 30 秒检查一次，到点则执行对应任务。"""
    global _executed_today, _last_date

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    hhmm  = now.strftime("%H:%M")
    weekday = now.weekday()  # 0=周一

    if today != _last_date:
        _executed_today.clear()
        _last_date = today
        log.info("📅 新的一天：%s", today)

    if weekday == 0 and hhmm == "08:00" and "earnings" not in _executed_today:
        _executed_today.add("earnings")
        run_earnings()

    if hhmm == "09:00" and "finance" not in _executed_today:
        _executed_today.add("finance")
        run_finance()

    if hhmm == "09:30" and "food" not in _executed_today:
        _executed_today.add("food")
        run_food()


def run_scheduler():
    """调度循环，每 30 秒检查一次时间（在独立线程中运行）。"""
    log.info("⏰ 调度器启动")
    log.info("   财经简报:   每天 09:00 → WxPusher")
    log.info("   餐饮趋势:   每天 09:30 → 飞书")
    log.info("   财报日历:   每周一 08:00 → WxPusher")
    while True:
        _check_and_run()
        time.sleep(30)


# ── 入口 ──────────────────────────────────────────────────────────────────────

_TASK_MAP = {
    "finance":  run_finance,
    "food":     run_food,
    "earnings": run_earnings,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lobster — 财经 & 餐饮日报调度器 + Agent 服务")
    parser.add_argument(
        "--now",
        metavar="TASK",
        help="立即执行指定任务：finance / food / earnings / all",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Agent HTTP 服务端口（默认 8765）",
    )
    args = parser.parse_args()

    if args.now:
        tasks = list(_TASK_MAP.values()) if args.now == "all" else [_TASK_MAP.get(args.now)]
        if not tasks[0]:
            print(f"未知任务 '{args.now}'，可选：finance / food / earnings / all")
            sys.exit(1)
        for task in tasks:
            task()
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
