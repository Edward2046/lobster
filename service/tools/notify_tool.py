# notify_tool.py — 统一通知工具

from smolagents import tool

from service.notifications import send_feishu, send_wxpusher


def send_notification_result(channel: str, title: str, content: str, *, markdown: bool = False) -> dict:
    channel = channel.strip().lower()
    if channel == "none":
        return {"ok": True, "message": "Notification skipped because channel is 'none'."}
    if channel == "wxpusher":
        ok = send_wxpusher(title, content, content_type=3 if markdown else 1)
        return {"ok": ok, "message": "WxPusher notification sent." if ok else "WxPusher notification failed."}
    if channel == "feishu":
        ok = send_feishu(title, content)
        return {"ok": ok, "message": "Feishu notification sent." if ok else "Feishu notification failed."}
    return {"ok": False, "message": f"Unsupported notification channel '{channel}'."}


@tool
def send_notification(channel: str, title: str, content: str) -> str:
    """Send a notification through WxPusher or Feishu.

    Args:
        channel: Notification channel: 'wxpusher', 'feishu', or 'none'.
        title: Notification title.
        content: Notification content.
    """
    return send_notification_result(channel, title, content)["message"]
