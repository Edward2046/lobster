# notify_tool.py — 统一通知工具

from smolagents import tool

from service.cron.notify import send_feishu, send_wxpusher


@tool
def send_notification(channel: str, title: str, content: str) -> str:
    """Send a notification through WxPusher or Feishu.

    Args:
        channel: Notification channel: 'wxpusher', 'feishu', or 'none'.
        title: Notification title.
        content: Notification content.
    """
    channel = channel.strip().lower()
    if channel == "none":
        return "Notification skipped because channel is 'none'."
    if channel == "wxpusher":
        ok = send_wxpusher(title, content)
        return "WxPusher notification sent." if ok else "WxPusher notification failed."
    if channel == "feishu":
        ok = send_feishu(title, content)
        return "Feishu notification sent." if ok else "Feishu notification failed."
    return f"Unsupported notification channel '{channel}'."
