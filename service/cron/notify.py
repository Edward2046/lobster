# cron/notify.py — 推送工具模块
#
# 封装两个推送渠道：
#   - WxPusher：发送到个人微信
#   - 飞书机器人：发送到飞书群

import os
import requests


def send_wxpusher(title: str, content: str) -> bool:
    """通过 WxPusher 推送消息到微信。

    Args:
        title:   消息标题
        content: 消息正文（支持 HTML）
    Returns:
        True 表示发送成功，False 表示失败
    """
    url = "https://wxpusher.zjiecode.com/api/send/message"
    payload = {
        "appToken": os.environ["WXPUSHER_APP_TOKEN"],
        "content": content,
        "summary": title,          # 微信通知栏显示的摘要
        "contentType": 1,          # 1=文本，2=HTML，3=Markdown
        "uids": [os.environ["WXPUSHER_UID"]],
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        success = result.get("success", False)
        if not success:
            print(f"[WxPusher] 发送失败: {result.get('msg')}")
        return success
    except Exception as e:
        print(f"[WxPusher] 请求异常: {e}")
        return False


def send_feishu(title: str, content: str) -> bool:
    """通过飞书机器人 Webhook 推送消息到飞书群。

    Args:
        title:   消息标题（加粗显示在正文顶部）
        content: 消息正文
    Returns:
        True 表示发送成功，False 表示失败
    """
    url = os.environ["FEISHU_WEBHOOK"]
    # 飞书 post 类型消息支持富文本，这里用简单的 text 类型
    payload = {
        "msg_type": "text",
        "content": {
            "text": f"【{title}】\n\n{content}"
        }
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        success = result.get("StatusCode", -1) == 0
        if not success:
            print(f"[飞书] 发送失败: {result.get('StatusMessage')}")
        return success
    except Exception as e:
        print(f"[飞书] 请求异常: {e}")
        return False
