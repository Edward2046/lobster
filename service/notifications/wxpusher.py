# notifications/wxpusher.py — WxPusher 推送模块

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
