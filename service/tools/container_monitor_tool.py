# container_monitor_tool.py — 容器监控工具

import subprocess
import json
from smolagents import tool

from config import settings


@tool
def get_container_metrics(container_name: str = "") -> str:
    """Monitor Docker container resource usage and health status.

    Use this to check CPU, memory, network, and disk I/O of containers.
    Works with both Docker and Kubernetes (via kubectl).

    Args:
        container_name: Container name or ID. If empty, lists all containers.
                       For Kubernetes, use format "pod-name" or "namespace/pod-name"

    Returns:
        Container metrics including CPU, memory, network, and health status.
    """
    lines = ["=== 容器监控 ===\n"]

    # 检测运行环境
    runtime = _detect_container_runtime()
    lines.append(f"【运行环境】{runtime}")
    lines.append("")

    if runtime == "Docker":
        return _monitor_docker_container(container_name, lines)
    elif runtime == "Kubernetes":
        return _monitor_k8s_pod(container_name, lines)
    else:
        return "❌ 未检测到容器运行时（Docker 或 Kubernetes）"


def _detect_container_runtime() -> str:
    """检测容器运行时环境"""
    # 检查 Docker
    try:
        result = subprocess.run(
            ["docker", "version"],
            capture_output=True,
            timeout=3
        )
        if result.returncode == 0:
            return "Docker"
    except Exception:
        pass

    # 检查 Kubernetes
    try:
        result = subprocess.run(
            ["kubectl", "version", "--client"],
            capture_output=True,
            timeout=3
        )
        if result.returncode == 0:
            return "Kubernetes"
    except Exception:
        pass

    return "None"


def _monitor_docker_container(container_name: str, lines: list) -> str:
    """监控 Docker 容器"""
    try:
        # 如果未指定容器名，列出所有容器
        if not container_name:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return "❌ 获取容器列表失败"

            containers = result.stdout.strip().split("\n")
            if not containers or not containers[0]:
                return "📭 当前没有运行中的容器"

            lines.append("【运行中的容器】")
            for container in containers:
                if container:
                    name, status, image = container.split("\t")
                    lines.append(f"  • {name}")
                    lines.append(f"    状态: {status}")
                    lines.append(f"    镜像: {image}")
            lines.append("")
            lines.append("💡 使用 get_container_metrics('容器名') 查看详细指标")
            return "\n".join(lines)

        # 检查容器是否存在
        result = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return f"❌ 容器不存在: {container_name}"

        inspect_data = json.loads(result.stdout)[0]

        # 基本信息
        lines.append(f"【容器信息】{container_name}")
        lines.append(f"  ID: {inspect_data['Id'][:12]}")
        lines.append(f"  镜像: {inspect_data['Config']['Image']}")
        lines.append(f"  状态: {inspect_data['State']['Status']}")
        lines.append(f"  运行时间: {inspect_data['State'].get('StartedAt', 'N/A')[:19]}")
        lines.append("")

        # 如果容器未运行，不获取资源指标
        if inspect_data['State']['Status'] != 'running':
            lines.append("⚠️ 容器未运行，无法获取资源指标")
            return "\n".join(lines)

        # 获取资源使用情况
        result = subprocess.run(
            ["docker", "stats", container_name, "--no-stream", "--format",
             "{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            stats = result.stdout.strip().split("\t")
            cpu_perc = stats[0]
            mem_usage = stats[1]
            mem_perc = stats[2]
            net_io = stats[3]
            block_io = stats[4]

            # CPU
            cpu_val = float(cpu_perc.rstrip('%'))
            cpu_status = "⚠️ 高负载" if cpu_val > settings.monitor.CPU_ALERT_THRESHOLD else "✅ 正常"
            lines.append(f"【CPU】{cpu_status}")
            lines.append(f"  使用率: {cpu_perc}")
            lines.append("")

            # 内存
            mem_val = float(mem_perc.rstrip('%'))
            mem_status = "⚠️ 内存紧张" if mem_val > settings.monitor.MEMORY_ALERT_THRESHOLD else "✅ 正常"
            lines.append(f"【内存】{mem_status}")
            lines.append(f"  使用率: {mem_perc}")
            lines.append(f"  用量: {mem_usage}")
            lines.append("")

            # 网络 I/O
            lines.append("【网络 I/O】")
            lines.append(f"  流量: {net_io}")
            lines.append("")

            # 磁盘 I/O
            lines.append("【磁盘 I/O】")
            lines.append(f"  读写: {block_io}")
            lines.append("")

        # 健康检查
        if 'Health' in inspect_data['State']:
            health = inspect_data['State']['Health']['Status']
            health_emoji = "✅" if health == "healthy" else "⚠️"
            lines.append(f"【健康检查】{health_emoji} {health}")
            lines.append("")

        # 重启次数
        restart_count = inspect_data['RestartCount']
        if restart_count > 0:
            lines.append(f"【重启次数】⚠️ {restart_count} 次")
            lines.append("")

        # 端口映射
        if inspect_data['NetworkSettings']['Ports']:
            lines.append("【端口映射】")
            for container_port, host_bindings in inspect_data['NetworkSettings']['Ports'].items():
                if host_bindings:
                    for binding in host_bindings:
                        lines.append(f"  {container_port} → {binding['HostIp']}:{binding['HostPort']}")
            lines.append("")

        # 健康评分
        lines.append("【健康评分】")
        issues = []
        if cpu_val > settings.monitor.CPU_ALERT_THRESHOLD:
            issues.append(f"CPU 使用率过高 ({cpu_perc})")
        if mem_val > settings.monitor.MEMORY_ALERT_THRESHOLD:
            issues.append(f"内存使用率过高 ({mem_perc})")
        if restart_count > settings.monitor.CONTAINER_RESTART_THRESHOLD:
            issues.append(f"重启次数过多 ({restart_count} 次)")

        if not issues:
            lines.append("✅ 容器运行正常")
        else:
            lines.append(f"⚠️ 发现 {len(issues)} 个问题:")
            for issue in issues:
                lines.append(f"  - {issue}")

    except subprocess.TimeoutExpired:
        return "❌ 命令执行超时"
    except Exception as e:
        return f"❌ 监控失败: {e}"

    return "\n".join(lines)


def _monitor_k8s_pod(pod_name: str, lines: list) -> str:
    """监控 Kubernetes Pod"""
    try:
        # 解析 namespace 和 pod 名称
        if "/" in pod_name:
            namespace, pod = pod_name.split("/", 1)
        else:
            namespace = "default"
            pod = pod_name

        # 如果未指定 pod，列出所有 pod
        if not pod:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-A", "-o",
                 "custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,STATUS:.status.phase,RESTARTS:.status.containerStatuses[0].restartCount"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                return "❌ 获取 Pod 列表失败"

            lines.append("【运行中的 Pods】")
            lines.append(result.stdout)
            lines.append("")
            lines.append("💡 使用 get_container_metrics('namespace/pod-name') 查看详细指标")
            return "\n".join(lines)

        # 获取 Pod 信息
        result = subprocess.run(
            ["kubectl", "get", "pod", pod, "-n", namespace, "-o", "json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return f"❌ Pod 不存在: {namespace}/{pod}"

        pod_data = json.loads(result.stdout)

        # 基本信息
        lines.append(f"【Pod 信息】{namespace}/{pod}")
        lines.append(f"  状态: {pod_data['status']['phase']}")
        lines.append(f"  节点: {pod_data['spec'].get('nodeName', 'N/A')}")
        lines.append(f"  创建时间: {pod_data['metadata']['creationTimestamp'][:19]}")
        lines.append("")

        # 容器状态
        lines.append("【容器状态】")
        for container in pod_data['status'].get('containerStatuses', []):
            name = container['name']
            ready = "✅" if container['ready'] else "❌"
            restart_count = container['restartCount']
            lines.append(f"  • {name} {ready}")
            lines.append(f"    重启次数: {restart_count}")
            if restart_count > 0:
                lines.append(f"    ⚠️ 容器已重启 {restart_count} 次")
        lines.append("")

        # 获取资源使用情况（需要 metrics-server）
        result = subprocess.run(
            ["kubectl", "top", "pod", pod, "-n", namespace, "--no-headers"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split()
            if len(parts) >= 3:
                cpu_usage = parts[1]
                mem_usage = parts[2]

                lines.append("【资源使用】")
                lines.append(f"  CPU: {cpu_usage}")
                lines.append(f"  内存: {mem_usage}")
                lines.append("")
        else:
            lines.append("【资源使用】")
            lines.append("  ⚠️ 无法获取资源指标（需要安装 metrics-server）")
            lines.append("")

        # 事件（最近的警告和错误）
        result = subprocess.run(
            ["kubectl", "get", "events", "-n", namespace,
             "--field-selector", f"involvedObject.name={pod}",
             "--sort-by", ".lastTimestamp", "-o", "json"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            events = json.loads(result.stdout).get('items', [])
            warning_events = [e for e in events if e['type'] in ['Warning', 'Error']]

            if warning_events:
                lines.append("【最近事件】")
                for event in warning_events[-5:]:  # 最近 5 条
                    event_type = event['type']
                    reason = event['reason']
                    message = event['message']
                    timestamp = event['lastTimestamp'][:19]
                    lines.append(f"  [{timestamp}] {event_type}: {reason}")
                    lines.append(f"    {message[:100]}")
                lines.append("")

        # 健康评分
        lines.append("【健康评分】")
        issues = []

        if pod_data['status']['phase'] != 'Running':
            issues.append(f"Pod 状态异常 ({pod_data['status']['phase']})")

        for container in pod_data['status'].get('containerStatuses', []):
            if not container['ready']:
                issues.append(f"容器 {container['name']} 未就绪")
            if container['restartCount'] > settings.monitor.CONTAINER_RESTART_THRESHOLD:
                issues.append(f"容器 {container['name']} 重启次数过多 ({container['restartCount']} 次)")

        if not issues:
            lines.append("✅ Pod 运行正常")
        else:
            lines.append(f"⚠️ 发现 {len(issues)} 个问题:")
            for issue in issues:
                lines.append(f"  - {issue}")

    except subprocess.TimeoutExpired:
        return "❌ 命令执行超时"
    except Exception as e:
        return f"❌ 监控失败: {e}"

    return "\n".join(lines)


@tool
def get_container_logs(
    container_name: str,
    lines: int = 100,
    since: str = "1h"
) -> str:
    """Get logs from a Docker container or Kubernetes pod.

    Args:
        container_name: Container/pod name. For K8s, use "namespace/pod-name"
        lines: Number of log lines to retrieve (default: 100)
        since: Time range, e.g., "1h", "30m", "24h" (default: "1h")

    Returns:
        Container/pod logs with timestamps.
    """
    runtime = _detect_container_runtime()

    try:
        if runtime == "Docker":
            result = subprocess.run(
                ["docker", "logs", container_name, "--tail", str(lines),
                 "--since", since, "--timestamps"],
                capture_output=True,
                text=True,
                timeout=10
            )
        elif runtime == "Kubernetes":
            if "/" in container_name:
                namespace, pod = container_name.split("/", 1)
            else:
                namespace = "default"
                pod = container_name

            result = subprocess.run(
                ["kubectl", "logs", pod, "-n", namespace,
                 f"--tail={lines}", f"--since={since}", "--timestamps"],
                capture_output=True,
                text=True,
                timeout=10
            )
        else:
            return "❌ 未检测到容器运行时"

        if result.returncode != 0:
            return f"❌ 获取日志失败: {result.stderr}"

        logs = result.stdout.strip()
        if not logs:
            return f"📭 最近 {since} 内没有日志"

        return f"=== 容器日志 ({container_name}) ===\n最近 {lines} 行 (时间范围: {since})\n\n{logs}"

    except subprocess.TimeoutExpired:
        return "❌ 命令执行超时"
    except Exception as e:
        return f"❌ 获取日志失败: {e}"
