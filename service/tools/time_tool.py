# time_tool.py — 时间查询工具

import datetime
import pytz
from smolagents import tool


@tool
def get_current_time(timezone: str = "Asia/Shanghai") -> str:
    """Get the current time in a given timezone.

    Args:
        timezone: IANA timezone name, e.g. 'Asia/Shanghai', 'America/New_York', 'Europe/London'.
    """
    try:
        # pytz.timezone() 将字符串解析为时区对象
        tz = pytz.timezone(timezone)
        # datetime.now(tz) 返回带时区信息的当前时间
        now = datetime.datetime.now(tz)
        # strftime 格式化输出，%Z 会展示时区缩写（如 CST、JST）
        return f"Current time in {timezone}: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    except pytz.exceptions.UnknownTimeZoneError:
        # 时区名称不合法时给出友好提示，而不是抛出异常
        # Agent 会读取这条错误信息并尝试修正参数后重试
        return f"Unknown timezone '{timezone}'. Try something like 'Asia/Shanghai' or 'America/New_York'."
