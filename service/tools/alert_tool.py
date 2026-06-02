# alert_tool.py — 智能告警工具

import os
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
from smolagents import tool


# 告警历史文件路径
ALERT_HISTORY_FILE = Path(__file__).parent.parent.parent / "data" / "alert_history.json"


def _load_alert_history() -> dict:
    """加载告警历史记录"""
    if not ALERT_HISTORY_FILE.exists():
        return {}
    try:
        with open(ALERT_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_alert_history(history: dict):
    """保存告警历史记录"""
    try:
        with open(ALERT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _should_send_alert(alert_key: str, dedupe_minutes: int = 60) -> bool:
    """检查是否应该发送告警（去重逻辑）"""
    history = _load_alert_history()
    last_sent = history.get(alert_key)

    if not last_sent:
        return True

    # 检查距离上次告警是否超过去重时间
    try:
        last_time = datetime.fromisoformat(last_sent)
        if datetime.now() - last_time < timedelta(minutes=dedupe_minutes):
            return False
    except Exception:
        pass

    return True


def _record_alert(alert_key: str):
    """记录告警发送时间"""
    history = _load_alert_history()
    history[alert_key] = datetime.now().isoformat()
    _save_alert_history(history)


@tool
def send_alert(
    title: str,
    message: str,
    level: str = "WARNING",
    dedupe_minutes: int = 60
) -> str:
    """Send an intelligent alert with automatic deduplication and channel selection.

    Use this to notify about system issues. Alerts are deduplicated to avoid spam.

    Args:
        title: Alert title (short summary)
        message: Detailed alert message
        level: Alert severity level. Options: 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
        dedupe_minutes: Deduplication window in minutes (default: 60). Same alert
                       won't be sent again within this time window.

    Returns:
        Status message indicating whether the alert was sent or deduplicated.
    """
    # 验证告警级别
    valid_levels = ["INFO", "WARNING", "ERROR", "CRITICAL"]
    level = level.upper()
    if level not in valid_levels:
        return f"无效的告警级别 '{level}'，可选: {', '.join(valid_levels)}"

    # 生成告警唯一键（用于去重）
    alert_key = f"{level}:{title}"

    # 检查是否需要去重
    if not _should_send_alert(alert_key, dedupe_minutes):
        return f"⏭️ 告警已去重（{dedupe_minutes} 分钟内已发送过相同告警）: {title}"

    # 根据级别选择通知渠道
    channels = []
    if level in ["INFO", "WARNING"]:
        channels = ["飞书"]
    elif level == "ERROR":
        channels = ["飞书", "微信"]
    elif level == "CRITICAL":
        channels = ["飞书", "微信", "邮件"]

    # 格式化告警消息
    level_emoji = {
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🚨"
    }
    emoji = level_emoji.get(level, "📢")

    formatted_message = f"{emoji} 【{level}】{title}\n\n{message}\n\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    # 发送告警
    results = []
    success_count = 0

    # 发送到飞书
    if "飞书" in channels:
        try:
            from service.notifications import send_feishu
            if send_feishu(title, formatted_message):
                results.append("✅ 飞书")
                success_count += 1
            else:
                results.append("❌ 飞书")
        except Exception as e:
            results.append(f"❌ 飞书 ({e})")

    # 发送到微信
    if "微信" in channels:
        try:
            from service.notifications import send_wxpusher
            if send_wxpusher(title, formatted_message):
                results.append("✅ 微信")
                success_count += 1
            else:
                results.append("❌ 微信")
        except Exception as e:
            results.append(f"❌ 微信 ({e})")

    # 发送到邮件（如果配置了）
    if "邮件" in channels:
        # TODO: 实现邮件发送
        results.append("⏭️ 邮件（未配置）")

    # 记录告警历史
    if success_count > 0:
        _record_alert(alert_key)

    # 返回结果
    status = f"📤 告警已发送 [{level}] {title}\n"
    status += f"通道: {' | '.join(results)}\n"
    status += f"成功: {success_count}/{len(channels)}"

    return status


@tool
def list_recent_alerts(hours: int = 24) -> str:
    """List recent alerts sent in the last N hours.

    Args:
        hours: Number of hours to look back (default: 24)

    Returns:
        List of recent alerts with timestamps.
    """
    history = _load_alert_history()
    if not history:
        return "📭 最近没有发送过告警"

    cutoff_time = datetime.now() - timedelta(hours=hours)
    recent_alerts = []

    for alert_key, timestamp_str in history.items():
        try:
            alert_time = datetime.fromisoformat(timestamp_str)
            if alert_time >= cutoff_time:
                time_ago = datetime.now() - alert_time
                minutes_ago = int(time_ago.total_seconds() / 60)
                if minutes_ago < 60:
                    time_str = f"{minutes_ago} 分钟前"
                else:
                    hours_ago = minutes_ago // 60
                    time_str = f"{hours_ago} 小时前"

                recent_alerts.append((alert_time, alert_key, time_str))
        except Exception:
            continue

    if not recent_alerts:
        return f"📭 最近 {hours} 小时内没有发送过告警"

    # 按时间倒序排列
    recent_alerts.sort(reverse=True)

    lines = [f"=== 最近 {hours} 小时的告警记录 ===\n"]
    for _, alert_key, time_str in recent_alerts:
        lines.append(f"• {alert_key} ({time_str})")

    lines.append(f"\n总计: {len(recent_alerts)} 条告警")

    return "\n".join(lines)
