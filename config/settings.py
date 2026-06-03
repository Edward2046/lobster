"""
config/settings.py — 统一配置中心

集中管理所有可配置项，支持从 .env 文件覆盖。

使用方式：
    from config.settings import settings
    print(settings.BACKEND_PORT)
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"


def _get_int(key: str, default: int) -> int:
    """从环境变量读取整数，失败返回默认值"""
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def _get_float(key: str, default: float) -> float:
    """从环境变量读取浮点数，失败返回默认值"""
    try:
        return float(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def _get_bool(key: str, default: bool) -> bool:
    """从环境变量读取布尔值"""
    value = os.environ.get(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


def _get_str(key: str, default: str) -> str:
    """从环境变量读取字符串"""
    return os.environ.get(key, default)


@dataclass
class ServerSettings:
    """HTTP 服务配置"""
    BACKEND_HOST: str = field(default_factory=lambda: _get_str("BACKEND_HOST", "0.0.0.0"))
    BACKEND_PORT: int = field(default_factory=lambda: _get_int("BACKEND_PORT", 8765))
    FRONTEND_PORT: int = field(default_factory=lambda: _get_int("FRONTEND_PORT", 5173))
    CORS_ORIGINS: list[str] = field(default_factory=lambda: ["*"])
    REQUEST_TIMEOUT: int = field(default_factory=lambda: _get_int("REQUEST_TIMEOUT", 60))


@dataclass
class AgentSettings:
    """Agent 配置"""
    MODEL_ID: str = field(default_factory=lambda: _get_str("AGENT_MODEL_ID", "deepseek/deepseek-reasoner"))
    MODEL_ID_FAST: str = field(default_factory=lambda: _get_str("AGENT_MODEL_ID_FAST", "deepseek/deepseek-chat"))
    MAX_STEPS: int = field(default_factory=lambda: _get_int("AGENT_MAX_STEPS", 15))
    VERBOSITY_LEVEL: int = field(default_factory=lambda: _get_int("AGENT_VERBOSITY_LEVEL", 1))
    TIMEOUT: int = field(default_factory=lambda: _get_int("AGENT_TIMEOUT", 30))
    NUM_RETRIES: int = field(default_factory=lambda: _get_int("AGENT_NUM_RETRIES", 0))
    DEEPSEEK_API_KEY: Optional[str] = field(default_factory=lambda: os.environ.get("DEEPSEEK_API_KEY"))
    STREAM_ENABLED: bool = field(default_factory=lambda: _get_bool("AGENT_STREAM_ENABLED", True))


@dataclass
class SchedulerSettings:
    """调度器配置"""
    SLEEP_SECONDS: int = field(default_factory=lambda: _get_int("SCHEDULER_SLEEP_SECONDS", 30))


@dataclass
class MemorySettings:
    """记忆系统配置"""
    DB_PATH: Path = field(default_factory=lambda: DATA_DIR / "memory.db")
    RECENT_LIMIT: int = field(default_factory=lambda: _get_int("MEMORY_RECENT_LIMIT", 5))
    RELEVANT_LIMIT: int = field(default_factory=lambda: _get_int("MEMORY_RELEVANT_LIMIT", 6))
    GOAL_LIMIT: int = field(default_factory=lambda: _get_int("MEMORY_GOAL_LIMIT", 3))
    REFLECTION_LIMIT: int = field(default_factory=lambda: _get_int("MEMORY_REFLECTION_LIMIT", 3))
    RETENTION_DAYS: int = field(default_factory=lambda: _get_int("MEMORY_RETENTION_DAYS", 90))
    # 向量检索配置
    VECTOR_ENABLED: bool = field(default_factory=lambda: _get_bool("MEMORY_VECTOR_ENABLED", False))
    VECTOR_MODEL: str = field(default_factory=lambda: _get_str("MEMORY_VECTOR_MODEL", "all-MiniLM-L6-v2"))
    VECTOR_TOP_K: int = field(default_factory=lambda: _get_int("MEMORY_VECTOR_TOP_K", 8))
    VECTOR_DB_PATH: Path = field(default_factory=lambda: DATA_DIR / "vectors.db")


@dataclass
class TaskSettings:
    """任务系统配置"""
    DB_PATH: Path = field(default_factory=lambda: DATA_DIR / "tasks.db")


@dataclass
class MonitorSettings:
    """监控告警配置"""
    CPU_ALERT_THRESHOLD: float = field(default_factory=lambda: _get_float("CPU_ALERT_THRESHOLD", 80.0))
    MEMORY_ALERT_THRESHOLD: float = field(default_factory=lambda: _get_float("MEMORY_ALERT_THRESHOLD", 85.0))
    DISK_ALERT_THRESHOLD: float = field(default_factory=lambda: _get_float("DISK_ALERT_THRESHOLD", 90.0))
    PROCESS_MEMORY_MB_THRESHOLD: int = field(default_factory=lambda: _get_int("PROCESS_MEMORY_MB_THRESHOLD", 500))
    DB_SIZE_MB_THRESHOLD: int = field(default_factory=lambda: _get_int("DB_SIZE_MB_THRESHOLD", 100))
    LOG_SIZE_MB_THRESHOLD: int = field(default_factory=lambda: _get_int("LOG_SIZE_MB_THRESHOLD", 100))
    CONTAINER_RESTART_THRESHOLD: int = field(default_factory=lambda: _get_int("CONTAINER_RESTART_THRESHOLD", 5))


@dataclass
class AlertSettings:
    """告警配置"""
    HISTORY_FILE: Path = field(default_factory=lambda: DATA_DIR / "alert_history.json")
    DEFAULT_DEDUPE_MINUTES: int = field(default_factory=lambda: _get_int("ALERT_DEDUPE_MINUTES", 60))


@dataclass
class NotificationSettings:
    """通知渠道配置"""
    WXPUSHER_APP_TOKEN: Optional[str] = field(default_factory=lambda: os.environ.get("WXPUSHER_APP_TOKEN"))
    WXPUSHER_UID: Optional[str] = field(default_factory=lambda: os.environ.get("WXPUSHER_UID"))
    FEISHU_WEBHOOK: Optional[str] = field(default_factory=lambda: os.environ.get("FEISHU_WEBHOOK"))
    REQUEST_TIMEOUT: int = field(default_factory=lambda: _get_int("NOTIFICATION_TIMEOUT", 10))


@dataclass
class ToolSettings:
    """工具配置"""
    TAVILY_API_KEY: Optional[str] = field(default_factory=lambda: os.environ.get("TAVILY_API_KEY"))
    HTTP_TIMEOUT: int = field(default_factory=lambda: _get_int("TOOL_HTTP_TIMEOUT", 10))


@dataclass
class LogSettings:
    """日志配置"""
    LOG_DIR: Path = field(default_factory=lambda: LOGS_DIR)
    LOG_FILE: Path = field(default_factory=lambda: LOGS_DIR / "lobster.log")
    LOG_LEVEL: str = field(default_factory=lambda: _get_str("LOG_LEVEL", "INFO"))
    LOG_FORMAT: str = field(
        default_factory=lambda: _get_str(
            "LOG_FORMAT",
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
    )
    LOG_DATE_FORMAT: str = field(default_factory=lambda: _get_str("LOG_DATE_FORMAT", "%Y-%m-%d %H:%M:%S"))
    BACKUP_DAYS: int = field(default_factory=lambda: _get_int("LOG_BACKUP_DAYS", 14))


@dataclass
class Settings:
    """全局配置入口"""
    server: ServerSettings = field(default_factory=ServerSettings)
    agent: AgentSettings = field(default_factory=AgentSettings)
    scheduler: SchedulerSettings = field(default_factory=SchedulerSettings)
    memory: MemorySettings = field(default_factory=MemorySettings)
    task: TaskSettings = field(default_factory=TaskSettings)
    monitor: MonitorSettings = field(default_factory=MonitorSettings)
    alert: AlertSettings = field(default_factory=AlertSettings)
    notification: NotificationSettings = field(default_factory=NotificationSettings)
    tool: ToolSettings = field(default_factory=ToolSettings)
    log: LogSettings = field(default_factory=LogSettings)

    PROJECT_ROOT: Path = field(default=PROJECT_ROOT)
    DATA_DIR: Path = field(default=DATA_DIR)
    LOGS_DIR: Path = field(default=LOGS_DIR)

    def __post_init__(self):
        """确保关键目录存在"""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)


# 全局单例
settings = Settings()
