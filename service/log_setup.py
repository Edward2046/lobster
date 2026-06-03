"""
service/log_setup.py — 统一日志配置入口

- 主日志文件：logs/lobster.log
- 每天 0 点滚动，归档文件名形如 logs/lobster.log.2026-06-03
- 同时输出到 stdout 和文件
- 通过 settings.log 配置等级、格式、保留天数
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

from config import settings


_initialized = False


def setup_logging(log_file: Optional[str] = None, *, force: bool = False) -> logging.Logger:
    """配置全局日志。多次调用幂等，除非 force=True。

    Args:
        log_file: 覆盖默认日志文件路径（settings.log.LOG_FILE）
        force:    强制重新配置（用于测试或动态切换）

    Returns:
        根 logger
    """
    global _initialized
    if _initialized and not force:
        return logging.getLogger()

    settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    target_file = log_file or str(settings.log.LOG_FILE)

    level = getattr(logging, settings.log.LOG_LEVEL.upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt=settings.log.LOG_FORMAT,
        datefmt=settings.log.LOG_DATE_FORMAT,
    )

    # 每天 0 点切分，保留 N 天历史；归档文件后缀为 YYYY-MM-DD
    file_handler = TimedRotatingFileHandler(
        filename=target_file,
        when="midnight",
        interval=1,
        backupCount=settings.log.BACKUP_DAYS,
        encoding="utf-8",
        utc=False,
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)

    root = logging.getLogger()
    root.setLevel(level)
    # 清理 basicConfig 留下的旧 handler，避免重复
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    _initialized = True
    return root
