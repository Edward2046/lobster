#!/usr/bin/env python3
"""
main.py — Lobster 项目入口

功能：
  - 作为常驻进程运行，内置调度器，无需依赖系统 crontab
  - 每天 09:00 推送财经简报（WxPusher）
  - 每天 09:30 推送餐饮趋势简报（飞书）
  - 每周一 08:00 推送一周财报日历（WxPusher）

用法：
  python main.py            # 启动常驻调度器
  python main.py --now all  # 立即执行全部任务（测试用）
  python main.py --now finance   # 立即执行财经简报
  python main.py --now food      # 立即执行餐饮趋势
  python main.py --now earnings  # 立即执行财报日历
"""

import sys
import time
import logging
import argparse
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
    from cron.daily_finance import build_report
    from cron.notify import send_wxpusher
    log.info("▶ 开始生成财经简报...")
    try:
        title, content = build_report()
        ok = send_wxpusher(title, content)
        log.info("✅ 财经简报推送%s", "成功" if ok else "失败")
    except Exception as e:
        log.error("❌ 财经简报异常: %s", e)


def run_food():
    """每天 09:30 — 餐饮趋势简报 → 飞书"""
    from cron.daily_food_trends import build_report
    from cron.notify import send_feishu
    log.info("▶ 开始生成餐饮趋势简报...")
    try:
        title, content = build_report()
        ok = send_feishu(title, content)
        log.info("✅ 餐饮趋势简报推送%s", "成功" if ok else "失败")
    except Exception as e:
        log.error("❌ 餐饮趋势简报异常: %s", e)


def run_earnings():
    """每周一 08:00 — 财报日历 → WxPusher"""
    from cron.weekly_earnings import build_report
    from cron.notify import send_wxpusher
    log.info("▶ 开始生成财报日历...")
    try:
        title, content = build_report()
        ok = send_wxpusher(title, content)
        log.info("✅ 财报日历推送%s", "成功" if ok else "失败")
    except Exception as e:
        log.error("❌ 财报日历异常: %s", e)


# ── 调度器 ────────────────────────────────────────────────────────────────────

# 记录今天已执行过的任务，避免同一天重复触发
_executed_today: set[str] = set()
_last_date: str = ""


def _check_and_run():
    """每分钟检查一次，到点则执行对应任务。"""
    global _executed_today, _last_date

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    hhmm  = now.strftime("%H:%M")
    weekday = now.weekday()  # 0=周一

    # 日期变更时重置已执行记录
    if today != _last_date:
        _executed_today.clear()
        _last_date = today
        log.info("📅 新的一天：%s", today)

    # 每周一 08:00 — 财报日历
    if weekday == 0 and hhmm == "08:00" and "earnings" not in _executed_today:
        _executed_today.add("earnings")
        run_earnings()

    # 每天 09:00 — 财经简报
    if hhmm == "09:00" and "finance" not in _executed_today:
        _executed_today.add("finance")
        run_finance()

    # 每天 09:30 — 餐饮趋势
    if hhmm == "09:30" and "food" not in _executed_today:
        _executed_today.add("food")
        run_food()


def run_scheduler():
    """启动常驻调度循环，每 30 秒检查一次时间。"""
    log.info("🦞 Lobster 调度器启动")
    log.info("   财经简报:   每天 09:00 → WxPusher")
    log.info("   餐饮趋势:   每天 09:30 → 飞书")
    log.info("   财报日历:   每周一 08:00 → WxPusher")
    log.info("   按 Ctrl+C 停止")

    try:
        while True:
            _check_and_run()
            time.sleep(30)  # 每 30 秒检查一次，精度足够
    except KeyboardInterrupt:
        log.info("🛑 调度器已停止")


# ── 入口 ──────────────────────────────────────────────────────────────────────

_TASK_MAP = {
    "finance":  run_finance,
    "food":     run_food,
    "earnings": run_earnings,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lobster — 财经 & 餐饮日报调度器")
    parser.add_argument(
        "--now",
        metavar="TASK",
        help="立即执行指定任务：finance / food / earnings / all",
    )
    args = parser.parse_args()

    if args.now:
        # 立即执行模式（测试用）
        tasks = list(_TASK_MAP.values()) if args.now == "all" else [_TASK_MAP.get(args.now)]
        if not tasks[0]:
            print(f"未知任务 '{args.now}'，可选：finance / food / earnings / all")
            sys.exit(1)
        for task in tasks:
            task()
    else:
        # 常驻调度模式
        run_scheduler()
