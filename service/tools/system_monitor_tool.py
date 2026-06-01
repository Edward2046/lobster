# system_monitor_tool.py — 系统资源监控工具

import psutil
import os
from smolagents import tool


@tool
def get_system_metrics() -> str:
    """Get current system resource usage metrics including CPU, memory, disk, and process info.

    Use this to monitor system health and detect resource issues before they cause problems.

    Returns:
        A formatted report of system metrics including usage percentages and warnings.
    """
    lines = ["=== 系统资源监控 ===\n"]

    # CPU 使用率
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    load_avg = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0, 0, 0)

    cpu_status = "⚠️ 高负载" if cpu_percent > 80 else "✅ 正常"
    lines.append(f"【CPU】{cpu_status}")
    lines.append(f"  使用率: {cpu_percent}%")
    lines.append(f"  核心数: {cpu_count}")
    lines.append(f"  负载: {load_avg[0]:.2f} (1分钟), {load_avg[1]:.2f} (5分钟), {load_avg[2]:.2f} (15分钟)")
    lines.append("")

    # 内存使用
    mem = psutil.virtual_memory()
    mem_used_gb = mem.used / (1024 ** 3)
    mem_total_gb = mem.total / (1024 ** 3)
    mem_status = "⚠️ 内存紧张" if mem.percent > 85 else "✅ 正常"

    lines.append(f"【内存】{mem_status}")
    lines.append(f"  使用率: {mem.percent}%")
    lines.append(f"  已用: {mem_used_gb:.2f} GB / {mem_total_gb:.2f} GB")
    lines.append(f"  可用: {mem.available / (1024 ** 3):.2f} GB")
    lines.append("")

    # 磁盘空间（检查根目录和数据库所在目录）
    lines.append("【磁盘空间】")

    # 根目录
    disk_root = psutil.disk_usage("/")
    root_status = "⚠️ 空间不足" if disk_root.percent > 90 else "✅ 正常"
    lines.append(f"  根目录 {root_status}")
    lines.append(f"    使用率: {disk_root.percent}%")
    lines.append(f"    已用: {disk_root.used / (1024 ** 3):.1f} GB / {disk_root.total / (1024 ** 3):.1f} GB")
    lines.append(f"    剩余: {disk_root.free / (1024 ** 3):.1f} GB")

    # 检查数据库所在目录
    try:
        db_path = os.path.join(os.getcwd(), "memory.db")
        if os.path.exists(db_path):
            db_dir = os.path.dirname(db_path)
            disk_db = psutil.disk_usage(db_dir)
            lines.append(f"  数据库目录: {disk_db.percent}% 使用")
    except Exception:
        pass

    lines.append("")

    # 进程信息
    process = psutil.Process(os.getpid())
    proc_mem = process.memory_info().rss / (1024 ** 2)  # MB
    proc_cpu = process.cpu_percent(interval=0.1)

    lines.append("【当前进程】")
    lines.append(f"  PID: {os.getpid()}")
    lines.append(f"  内存: {proc_mem:.1f} MB")
    lines.append(f"  CPU: {proc_cpu}%")
    lines.append(f"  线程数: {process.num_threads()}")

    # 检查是否有内存泄漏风险（进程内存超过 500MB）
    if proc_mem > 500:
        lines.append(f"  ⚠️ 警告: 进程内存较高 ({proc_mem:.1f} MB)，可能存在内存泄漏")

    lines.append("")

    # 系统进程统计
    total_procs = len(psutil.pids())
    lines.append(f"【系统进程】总计 {total_procs} 个进程")

    # 总体健康评分
    lines.append("\n【健康评分】")
    issues = []
    if cpu_percent > 80:
        issues.append("CPU 负载过高")
    if mem.percent > 85:
        issues.append("内存使用过高")
    if disk_root.percent > 90:
        issues.append("磁盘空间不足")
    if proc_mem > 500:
        issues.append("进程内存过高")

    if not issues:
        lines.append("✅ 系统运行正常")
    else:
        lines.append(f"⚠️ 发现 {len(issues)} 个问题:")
        for issue in issues:
            lines.append(f"  - {issue}")

    return "\n".join(lines)
