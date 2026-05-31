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

from dotenv import load_dotenv
import schedule
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


def run_scheduler():
    """调度循环（在独立线程中运行）。"""
    log.info("⏰ 调度器启动")
    log.info("   财经简报:   每天 09:00 → WxPusher")
    log.info("   餐饮趋势:   每天 09:30 → 飞书")
    log.info("   财报日历:   每周一 08:00 → WxPusher")

    schedule.every().day.at("09:00").do(run_finance)
    schedule.every().day.at("09:30").do(run_food)
    schedule.every().monday.at("08:00").do(run_earnings)

    while True:
        schedule.run_pending()
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
        if args.now == "all":
            tasks = list(_TASK_MAP.values())
        elif args.now in _TASK_MAP:
            tasks = [_TASK_MAP[args.now]]
        else:
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
