"""
service/reports/log_monitor.py — 错误日志监控告警生成器

判据（双判据）：
  1. 阈值告警：当前窗口错误数 >= settings.log_monitor.ABS_THRESHOLD
  2. 突增告警：当前窗口错误数 >= MIN_BASELINE_COUNT
                且 当前 / 历史均值 >= SPIKE_RATIO

两者命中任一即出告警，全部命中升级为 ERROR 级。

任务参数（task_params）：
  {
    "report_type": "log_monitor",
    "app_id": "payment-gateway",         # 必填
    "abs_threshold": 50,                  # 可选，覆盖全局
    "spike_ratio": 3.0,                   # 可选
    "min_baseline_count": 5,              # 可选
    "window_minutes": 5,                  # 可选
    "baseline_windows": 12,               # 可选
    "markdown": true                      # 可选
  }

返回 (title, content)；如果未触发任何告警，返回 (None, None) 让 handler 跳过推送。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from config import settings
from service.tools.es_log_monitor_tool import (
    count_error_logs,
    fetch_recent_errors,
)


def _evaluate(
    app_id: str,
    window_minutes: int,
    baseline_windows: int,
    abs_threshold: int,
    spike_ratio: float,
    min_baseline_count: int,
) -> dict:
    """统计当前窗口错误数 + 基线均值，给出告警判定。

    返回字典：
      {
        "current": int,
        "baseline_avg": float,
        "baseline_max": int,
        "abs_alert": bool,
        "spike_alert": bool,
        "level": "INFO" | "WARNING" | "ERROR",
        "samples": [..],
        "error": Optional[str],   # 查询失败时
      }
    """
    now = datetime.now(timezone.utc)
    current_start = now - timedelta(minutes=window_minutes)
    current_count = count_error_logs(app_id, current_start, now)
    if current_count < 0:
        return {"error": "ES 查询失败"}

    # 历史窗口均值（不包含当前窗口）
    baseline_counts: list[int] = []
    for i in range(1, baseline_windows + 1):
        end = now - timedelta(minutes=window_minutes * i)
        start = end - timedelta(minutes=window_minutes)
        c = count_error_logs(app_id, start, end)
        if c >= 0:
            baseline_counts.append(c)

    baseline_avg = sum(baseline_counts) / len(baseline_counts) if baseline_counts else 0.0
    baseline_max = max(baseline_counts) if baseline_counts else 0

    abs_alert = current_count >= abs_threshold
    spike_alert = (
        current_count >= min_baseline_count
        and baseline_avg > 0
        and (current_count / baseline_avg) >= spike_ratio
    )

    if abs_alert and spike_alert:
        level = "ERROR"
    elif abs_alert or spike_alert:
        level = "WARNING"
    else:
        level = "INFO"

    samples: list[dict] = []
    if abs_alert or spike_alert:
        samples = fetch_recent_errors(
            app_id,
            current_start,
            now,
            size=settings.log_monitor.SAMPLE_SIZE,
        )

    return {
        "current": current_count,
        "baseline_avg": baseline_avg,
        "baseline_max": baseline_max,
        "baseline_counts": baseline_counts,
        "abs_alert": abs_alert,
        "spike_alert": spike_alert,
        "level": level,
        "samples": samples,
    }


def _format_markdown(app_id: str, window_minutes: int, result: dict, params: dict) -> str:
    current = result["current"]
    avg = result["baseline_avg"]
    spike_x = (current / avg) if avg > 0 else 0
    abs_alert = result["abs_alert"]
    spike_alert = result["spike_alert"]

    reasons = []
    if abs_alert:
        reasons.append(f"绝对量 {current} ≥ 阈值 {params['abs_threshold']}")
    if spike_alert:
        reasons.append(f"突增 {spike_x:.1f}× ≥ {params['spike_ratio']}×（基线均值 {avg:.1f}）")

    lines = [
        f"### 触发原因",
        *[f"- {r}" for r in reasons],
        "",
        f"### 关键指标",
        f"- 服务：`{app_id}`",
        f"- 窗口：最近 {window_minutes} 分钟",
        f"- 当前错误数：**{current}**",
        f"- 历史基线均值：{avg:.1f}（取过去 {len(result['baseline_counts'])} 个窗口）",
        f"- 历史基线最大：{result['baseline_max']}",
        "",
    ]

    samples = result.get("samples") or []
    if samples:
        lines.append("### 样例错误日志")
        for i, doc in enumerate(samples, start=1):
            ts = doc.get(settings.es.TIMESTAMP_FIELD, "")
            level = doc.get(settings.es.LEVEL_FIELD, "")
            msg = (doc.get(settings.es.MESSAGE_FIELD) or "").strip().replace("\n", " ")
            lines.append(f"{i}. `[{ts}]` {level} — {msg[:160]}")
            trace = doc.get("trace_id")
            if trace:
                lines.append(f"   trace_id: `{trace}`")
        lines.append("")

    lines.append("> 告警由 Lobster 错误日志监控触发，建议结合 trace_id 进一步排查。")
    return "\n".join(lines)


def build_report(params: Optional[dict] = None) -> tuple[Optional[str], Optional[str]]:
    """生成日志监控告警简报。未触发则返回 (None, None)。"""
    params = params or {}
    app_id = params.get("app_id")
    if not app_id:
        raise ValueError("log_monitor task requires 'app_id' in task_params")

    cfg = settings.log_monitor
    window_minutes = int(params.get("window_minutes", cfg.WINDOW_MINUTES))
    baseline_windows = int(params.get("baseline_windows", cfg.BASELINE_WINDOWS))
    abs_threshold = int(params.get("abs_threshold", cfg.ABS_THRESHOLD))
    spike_ratio = float(params.get("spike_ratio", cfg.SPIKE_RATIO))
    min_baseline_count = int(params.get("min_baseline_count", cfg.MIN_BASELINE_COUNT))

    eval_params = {
        "abs_threshold": abs_threshold,
        "spike_ratio": spike_ratio,
        "min_baseline_count": min_baseline_count,
    }

    result = _evaluate(
        app_id=app_id,
        window_minutes=window_minutes,
        baseline_windows=baseline_windows,
        **eval_params,
    )

    if "error" in result:
        # 查询失败本身也是问题，发一个 WARNING 级提醒，避免静默失效
        title = f"⚠️ 日志监控异常 · {app_id}"
        content = (
            f"# {title}\n\n"
            f"无法查询 Elasticsearch（app_id=`{app_id}`），监控暂时失效。\n"
            f"请检查 ES 连通性与配置。"
        )
        return title, content

    if not (result["abs_alert"] or result["spike_alert"]):
        return None, None  # 无告警

    severity_emoji = {"WARNING": "⚠️", "ERROR": "🚨"}.get(result["level"], "ℹ️")
    title = f"{severity_emoji} 错误日志告警 · {app_id} · {result['level']}"
    body = _format_markdown(app_id, window_minutes, result, eval_params)
    content = f"# {title}\n\n{body}"
    return title, content
