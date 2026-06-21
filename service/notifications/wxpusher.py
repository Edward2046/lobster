# notifications/wxpusher.py — WxPusher 推送模块

import os

import requests


def _parse_wxpusher_uids(raw_uids: str) -> list[str]:
    seen = set()
    parsed_uids = []
    for item in raw_uids.split(","):
        uid = item.strip()
        if uid and uid not in seen:
            seen.add(uid)
            parsed_uids.append(uid)
    return parsed_uids


def _get_wxpusher_uids() -> list[str]:
    multi_uids = _parse_wxpusher_uids(os.environ.get("WXPUSHER_UIDS", ""))
    if multi_uids:
        return multi_uids

    single_uid = _parse_wxpusher_uids(os.environ.get("WXPUSHER_UID", ""))
    if single_uid:
        return single_uid

    raise KeyError("WXPUSHER_UIDS")


def send_wxpusher(title: str, content: str, content_type: int = 1) -> bool:
    """通过 WxPusher 推送消息到微信。

    Args:
        title:   消息标题
        content: 消息正文
        content_type: 1=文本，2=HTML，3=Markdown（markdown 模式下 [文本](url) 可点击）
    Returns:
        True 表示发送成功，False 表示失败
    """
    url = "https://wxpusher.zjiecode.com/api/send/message"
    try:
        payload = {
            "appToken": os.environ["WXPUSHER_APP_TOKEN"],
            "content": content,
            "summary": title,          # 微信通知栏显示的摘要
            "contentType": content_type,
            "uids": _get_wxpusher_uids(),
        }
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        success = result.get("success", False)
        if not success:
            print(f"[WxPusher] 发送失败: {result.get('msg')}")
        return success
    except KeyError:
        print("[WxPusher] 缺少环境变量：请配置 WXPUSHER_APP_TOKEN，以及 WXPUSHER_UIDS 或 WXPUSHER_UID。")
        return False
    except Exception as e:
        print(f"[WxPusher] 请求异常: {e}")
        return False
