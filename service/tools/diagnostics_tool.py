# diagnostics_tool.py — 一键诊断工具

from smolagents import tool


@tool
def run_diagnostics(include_cleanup: bool = False) -> str:
    """Run comprehensive system diagnostics including all health checks.

    This is a one-stop tool to quickly assess overall system health.
    It runs all monitoring tools and generates a unified report.

    Args:
        include_cleanup: If True, automatically clean up old data (30+ days) if issues found

    Returns:
        Comprehensive diagnostic report with health scores and recommendations.
    """
    from service.tools.system_monitor_tool import get_system_metrics
    from service.tools.log_analyzer_tool import analyze_logs
    from service.tools.database_health_tool import check_database_health

    lines = ["=" * 60]
    lines.append("🔍 Lobster 系统诊断报告")
    lines.append("=" * 60)
    lines.append("")

    # 记录开始时间
    from datetime import datetime
    start_time = datetime.now()
    lines.append(f"诊断时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # 1. 系统资源监控
    lines.append("━" * 60)
    lines.append("【1/4】系统资源监控")
    lines.append("━" * 60)
    try:
        system_report = get_system_metrics()
        lines.append(system_report)
    except Exception as e:
        lines.append(f"❌ 系统监控失败: {e}")
    lines.append("")

    # 2. 日志分析
    lines.append("━" * 60)
    lines.append("【2/4】日志分析")
    lines.append("━" * 60)
    try:
        log_report = analyze_logs(hours=24, error_only=False)
        lines.append(log_report)
    except Exception as e:
        lines.append(f"❌ 日志分析失败: {e}")
    lines.append("")

    # 3. 数据库健康检查
    lines.append("━" * 60)
    lines.append("【3/4】数据库健康检查")
    lines.append("━" * 60)
    try:
        cleanup_days = 30 if include_cleanup else 0
        db_report = check_database_health(cleanup_days=cleanup_days)
        lines.append(db_report)
    except Exception as e:
        lines.append(f"❌ 数据库检查失败: {e}")
    lines.append("")

    # 4. 网络连通性检查
    lines.append("━" * 60)
    lines.append("【4/4】网络连通性检查")
    lines.append("━" * 60)
    try:
        network_report = _check_network_connectivity()
        lines.append(network_report)
    except Exception as e:
        lines.append(f"❌ 网络检查失败: {e}")
    lines.append("")

    # 总结
    lines.append("=" * 60)
    lines.append("【诊断总结】")
    lines.append("=" * 60)

    # 收集所有问题
    full_report = "\n".join(lines)
    issues = []

    if "⚠️" in full_report or "❌" in full_report:
        # 系统资源问题
        if "CPU 负载过高" in full_report or "内存使用过高" in full_report:
            issues.append("系统资源紧张")
        if "磁盘空间不足" in full_report:
            issues.append("磁盘空间不足")

        # 日志问题
        if "错误率过高" in full_report or "错误数量过多" in full_report:
            issues.append("日志中存在大量错误")

        # 数据库问题
        if "数据库较大" in full_report:
            issues.append("数据库文件较大")
        if "查询性能较慢" in full_report:
            issues.append("数据库查询性能下降")

        # 网络问题
        if "API 不可达" in full_report or "连接失败" in full_report:
            issues.append("外部服务连通性异常")

    if not issues:
        lines.append("✅ 系统整体运行正常，未发现严重问题")
    else:
        lines.append(f"⚠️ 发现 {len(issues)} 类问题:")
        for i, issue in enumerate(issues, 1):
            lines.append(f"  {i}. {issue}")

    lines.append("")

    # 自动修复建议
    if issues:
        lines.append("【自动修复建议】")

        if "数据库文件较大" in issues or "数据库查询性能下降" in issues:
            if include_cleanup:
                lines.append("  ✅ 已自动清理 30 天前的旧数据")
            else:
                lines.append("  💡 运行 run_diagnostics(include_cleanup=True) 自动清理旧数据")

        if "系统资源紧张" in issues:
            lines.append("  💡 考虑重启服务释放资源")

        if "日志中存在大量错误" in issues:
            lines.append("  💡 使用 analyze_logs(keyword='ERROR') 查看详细错误")

        if "外部服务连通性异常" in issues:
            lines.append("  💡 检查网络连接和 API 配置")

        lines.append("")

    # 耗时统计
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    lines.append(f"诊断耗时: {duration:.2f} 秒")
    lines.append("=" * 60)

    return "\n".join(lines)


def _check_network_connectivity() -> str:
    """检查外部服务连通性（内部辅助函数）"""
    import requests

    lines = ["=== 网络连通性检查 ===\n"]

    # 检查的服务列表
    services = [
        {
            "name": "DeepSeek API",
            "url": "https://api.deepseek.com",
            "timeout": 5
        },
        {
            "name": "英为财经 RSS",
            "url": "https://cn.investing.com/rss/news.rss",
            "timeout": 5
        },
        {
            "name": "Open-Meteo 天气 API",
            "url": "https://api.open-meteo.com/v1/forecast?latitude=39.9&longitude=116.4&current_weather=true",
            "timeout": 5
        },
        {
            "name": "Nasdaq 财报 API",
            "url": "https://api.nasdaq.com/api/calendar/earnings",
            "timeout": 5
        }
    ]

    success_count = 0
    total_count = len(services)

    for service in services:
        try:
            response = requests.get(
                service["url"],
                timeout=service["timeout"],
                headers={"User-Agent": "Mozilla/5.0"}
            )
            response_time = response.elapsed.total_seconds() * 1000  # ms

            if response.status_code < 400:
                status = "✅ 正常"
                success_count += 1
            else:
                status = f"⚠️ HTTP {response.status_code}"

            lines.append(f"{service['name']}: {status} ({response_time:.0f} ms)")

        except requests.exceptions.Timeout:
            lines.append(f"{service['name']}: ❌ 超时")
        except requests.exceptions.ConnectionError:
            lines.append(f"{service['name']}: ❌ 连接失败")
        except Exception as e:
            lines.append(f"{service['name']}: ❌ {type(e).__name__}")

    lines.append("")
    lines.append(f"【连通性统计】{success_count}/{total_count} 个服务可用")

    if success_count == total_count:
        lines.append("✅ 所有外部服务连通正常")
    elif success_count > 0:
        lines.append(f"⚠️ 部分服务不可用 ({total_count - success_count} 个)")
    else:
        lines.append("❌ 所有外部服务均不可用，请检查网络连接")

    return "\n".join(lines)
