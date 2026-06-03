"""
service/tools/es_log_monitor_tool.py — Elasticsearch 错误日志查询

只负责查询，不做告警判断。供 reports/log_monitor.py 编排调用。

约定：
  - 索引由 settings.es.INDEX_PATTERN 决定，{app_id} 可被替换
  - 错误日志判定字段由 settings.es.LEVEL_FIELD 决定，默认认为 ERROR / FATAL
  - 时间戳字段由 settings.es.TIMESTAMP_FIELD 决定
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from smolagents import tool

from config import settings


def _auth() -> tuple[Optional[tuple[str, str]], dict]:
    """根据配置返回 requests 用的 auth tuple 和 headers。"""
    headers = {"Content-Type": "application/json"}
    if settings.es.API_KEY:
        headers["Authorization"] = f"ApiKey {settings.es.API_KEY}"
        return None, headers
    if settings.es.USERNAME and settings.es.PASSWORD:
        return (settings.es.USERNAME, settings.es.PASSWORD), headers
    return None, headers


def _index_for(app_id: str) -> str:
    return settings.es.INDEX_PATTERN.format(app_id=app_id)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _build_error_query(app_id: str, start: datetime, end: datetime) -> dict:
    """构造 ES query DSL：按 app_id + 时间范围 + 错误级别筛选。"""
    return {
        "bool": {
            "filter": [
                {"term": {settings.es.APP_FIELD: app_id}},
                {
                    "terms": {
                        # 同时兼容大小写和常见拼写
                        settings.es.LEVEL_FIELD: ["ERROR", "error", "Error", "FATAL", "fatal"],
                    }
                },
                {
                    "range": {
                        settings.es.TIMESTAMP_FIELD: {
                            "gte": _iso(start),
                            "lte": _iso(end),
                        }
                    }
                },
            ]
        }
    }


def count_error_logs(app_id: str, start: datetime, end: datetime) -> int:
    """查询时间窗口内 app_id 的错误日志数量。

    返回 -1 表示查询失败（让上层决定是降级还是告警）。
    """
    url = f"{settings.es.BASE_URL.rstrip('/')}/{_index_for(app_id)}/_count"
    auth, headers = _auth()
    payload = {"query": _build_error_query(app_id, start, end)}
    try:
        resp = requests.post(
            url,
            json=payload,
            auth=auth,
            headers=headers,
            timeout=settings.es.TIMEOUT,
        )
        resp.raise_for_status()
        return int(resp.json().get("count", 0))
    except requests.exceptions.RequestException:
        return -1
    except (ValueError, KeyError):
        return -1


def fetch_recent_errors(
    app_id: str,
    start: datetime,
    end: datetime,
    size: int = 5,
) -> list[dict]:
    """抓取窗口内最近 N 条错误日志样例。"""
    url = f"{settings.es.BASE_URL.rstrip('/')}/{_index_for(app_id)}/_search"
    auth, headers = _auth()
    payload = {
        "query": _build_error_query(app_id, start, end),
        "size": size,
        "sort": [{settings.es.TIMESTAMP_FIELD: {"order": "desc"}}],
        "_source": [
            settings.es.TIMESTAMP_FIELD,
            settings.es.LEVEL_FIELD,
            settings.es.MESSAGE_FIELD,
            "logger",
            "stack_trace",
            "trace_id",
        ],
    }
    try:
        resp = requests.post(
            url,
            json=payload,
            auth=auth,
            headers=headers,
            timeout=settings.es.TIMEOUT,
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])
        return [hit.get("_source", {}) for hit in hits]
    except requests.exceptions.RequestException:
        return []
    except (ValueError, KeyError):
        return []


@tool
def query_app_error_logs(app_id: str, minutes: int = 5, size: int = 5) -> str:
    """Query recent ERROR/FATAL logs for a given app from Elasticsearch.

    Use this to inspect what errors a service has produced in the last N minutes.

    Args:
        app_id: Application identifier as stored in the ES `app_id` field.
        minutes: Look-back window in minutes. Default 5.
        size: Maximum number of sample log lines to return. Default 5.

    Returns:
        A formatted summary including total error count and sample log lines.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=minutes)

    total = count_error_logs(app_id, start, end)
    if total < 0:
        return f"❌ 查询 ES 失败（app_id={app_id}），请检查 ES_BASE_URL / 鉴权配置。"

    samples = fetch_recent_errors(app_id, start, end, size=size) if total > 0 else []

    lines = [
        f"=== {app_id} 最近 {minutes} 分钟错误日志 ===",
        f"总数：{total} 条",
        "",
    ]
    if samples:
        lines.append(f"【样例（最新 {len(samples)} 条）】")
        for i, doc in enumerate(samples, start=1):
            ts = doc.get(settings.es.TIMESTAMP_FIELD, "")
            level = doc.get(settings.es.LEVEL_FIELD, "")
            msg = (doc.get(settings.es.MESSAGE_FIELD) or "").strip().replace("\n", " ")
            trace = doc.get("trace_id", "")
            lines.append(f"{i}. [{ts}] {level} {msg[:200]}")
            if trace:
                lines.append(f"   trace_id={trace}")
    else:
        lines.append("（窗口内无错误日志）")

    return "\n".join(lines)
