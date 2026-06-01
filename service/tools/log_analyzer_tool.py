# log_analyzer_tool.py — 日志分析工具

import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter
from smolagents import tool


@tool
def analyze_logs(
    log_file: str = "lobster.log",
    hours: int = 24,
    keyword: str = "",
    error_only: bool = False
) -> str:
    """Analyze application logs to identify errors, warnings, and patterns.

    Use this to quickly diagnose issues by examining recent log entries.

    Args:
        log_file: Path to log file (default: "lobster.log")
        hours: Analyze logs from the last N hours (default: 24)
        keyword: Optional keyword to filter logs (e.g., "timeout", "failed")
        error_only: If True, only show ERROR and CRITICAL level logs

    Returns:
        Analysis report including error counts, recent errors, and log statistics.
    """
    log_path = Path(log_file)
    if not log_path.exists():
        return f"日志文件不存在: {log_file}"

    # 检查日志文件大小
    file_size_mb = log_path.stat().st_size / (1024 ** 2)
    if file_size_mb > 100:
        size_warning = f"⚠️ 日志文件较大 ({file_size_mb:.1f} MB)，建议归档"
    else:
        size_warning = f"日志文件大小: {file_size_mb:.2f} MB"

    lines = [f"=== 日志分析报告 ({log_file}) ===\n"]
    lines.append(size_warning)
    lines.append("")

    # 读取日志
    cutoff_time = datetime.now() - timedelta(hours=hours)

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            log_lines = f.readlines()
    except Exception as e:
        return f"读取日志文件失败: {e}"

    # 解析日志
    errors = []
    warnings = []
    infos = []
    all_levels = Counter()
    error_types = Counter()

    for line in log_lines:
        line = line.strip()
        if not line:
            continue

        # 尝试解析时间戳（格式：2024-05-28 15:30:45）
        try:
            timestamp_str = line[:19]
            log_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            if log_time < cutoff_time:
                continue
        except (ValueError, IndexError):
            # 无法解析时间戳，跳过时间过滤
            pass

        # 关键词过滤
        if keyword and keyword.lower() not in line.lower():
            continue

        # 日志级别统计
        if "[ERROR]" in line or "[CRITICAL]" in line:
            errors.append(line)
            all_levels["ERROR"] += 1
            # 提取错误类型
            if ":" in line:
                error_msg = line.split(":", 2)[-1].strip()
                error_type = error_msg.split()[0] if error_msg else "Unknown"
                error_types[error_type] += 1
        elif "[WARNING]" in line or "[WARN]" in line:
            warnings.append(line)
            all_levels["WARNING"] += 1
        elif "[INFO]" in line:
            infos.append(line)
            all_levels["INFO"] += 1

    # 生成报告
    lines.append(f"【时间范围】最近 {hours} 小时")
    if keyword:
        lines.append(f"【过滤关键词】{keyword}")
    lines.append("")

    # 日志级别统计
    lines.append("【日志级别统计】")
    total_logs = sum(all_levels.values())
    if total_logs == 0:
        lines.append("  未找到符合条件的日志")
        return "\n".join(lines)

    for level in ["ERROR", "WARNING", "INFO"]:
        count = all_levels.get(level, 0)
        percentage = (count / total_logs * 100) if total_logs > 0 else 0
        lines.append(f"  {level}: {count} 条 ({percentage:.1f}%)")
    lines.append(f"  总计: {total_logs} 条")
    lines.append("")

    # 错误类型统计
    if error_types:
        lines.append("【错误类型 Top 5】")
        for error_type, count in error_types.most_common(5):
            lines.append(f"  {error_type}: {count} 次")
        lines.append("")

    # 最近的错误日志
    if errors:
        lines.append(f"【最近的错误日志】(共 {len(errors)} 条，显示最新 10 条)")
        for error in errors[-10:]:
            # 截断过长的日志
            if len(error) > 150:
                error = error[:150] + "..."
            lines.append(f"  {error}")
        lines.append("")
    else:
        lines.append("【最近的错误日志】✅ 无错误日志")
        lines.append("")

    # 警告日志（如果不是只看错误）
    if not error_only and warnings:
        lines.append(f"【最近的警告日志】(共 {len(warnings)} 条，显示最新 5 条)")
        for warning in warnings[-5:]:
            if len(warning) > 150:
                warning = warning[:150] + "..."
            lines.append(f"  {warning}")
        lines.append("")

    # 健康评估
    lines.append("【健康评估】")
    issues = []

    error_rate = (all_levels.get("ERROR", 0) / total_logs * 100) if total_logs > 0 else 0
    if error_rate > 10:
        issues.append(f"错误率过高 ({error_rate:.1f}%)")

    if len(errors) > 50:
        issues.append(f"错误数量过多 ({len(errors)} 条)")

    if file_size_mb > 100:
        issues.append(f"日志文件过大 ({file_size_mb:.1f} MB)")

    if not issues:
        lines.append("✅ 日志健康状况良好")
    else:
        lines.append(f"⚠️ 发现 {len(issues)} 个问题:")
        for issue in issues:
            lines.append(f"  - {issue}")

    return "\n".join(lines)
