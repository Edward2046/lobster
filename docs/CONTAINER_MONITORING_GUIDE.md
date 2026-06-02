# 容器监控工具使用指南

## 概述

Lobster 现已支持 Docker 和 Kubernetes 容器监控，可以监控部署在容器平台的服务（如 xxx-service）。

## 工具列表

### 1. get_container_metrics() - 容器资源监控

**支持平台**:
- ✅ Docker
- ✅ Kubernetes (需要 kubectl 和 metrics-server)

**功能**:
- CPU 使用率监控
- 内存使用情况
- 网络 I/O 统计
- 磁盘 I/O 统计
- 容器健康状态
- 重启次数统计
- 端口映射信息

---

### 2. get_container_logs() - 容器日志查看

**功能**:
- 查看容器/Pod 日志
- 支持时间范围过滤
- 支持行数限制
- 带时间戳输出

---

## 使用方式

### Docker 环境

#### 1. 列出所有运行中的容器
```python
get_container_metrics()
```

**输出示例**:
```
=== 容器监控 ===

【运行环境】Docker

【运行中的容器】
  • my-redis
    状态: Up 12 days
    镜像: redis
  • xxx-service
    状态: Up 3 days
    镜像: myapp:latest

💡 使用 get_container_metrics('容器名') 查看详细指标
```

#### 2. 监控特定容器
```python
get_container_metrics('xxx-service')
```

**输出示例**:
```
=== 容器监控 ===

【运行环境】Docker

【容器信息】xxx-service
  ID: abc123def456
  镜像: myapp:latest
  状态: running
  运行时间: 2026-05-28T10:00:00

【CPU】✅ 正常
  使用率: 15.5%

【内存】✅ 正常
  使用率: 45.2%
  用量: 512MiB / 1GiB

【网络 I/O】
  流量: 1.2MB / 850KB

【磁盘 I/O】
  读写: 50MB / 20MB

【端口映射】
  8080/tcp → 0.0.0.0:8080

【健康评分】
✅ 容器运行正常
```

#### 3. 查看容器日志
```python
# 查看最近 100 行日志（最近 1 小时）
get_container_logs('xxx-service')

# 查看最近 500 行日志（最近 24 小时）
get_container_logs('xxx-service', lines=500, since='24h')

# 查看最近 30 分钟的日志
get_container_logs('xxx-service', since='30m')
```

---

### Kubernetes 环境

#### 1. 列出所有 Pods
```python
get_container_metrics()
```

**输出示例**:
```
=== 容器监控 ===

【运行环境】Kubernetes

【运行中的 Pods】
NAMESPACE     NAME                    STATUS    RESTARTS
default       xxx-service-abc123      Running   0
production    api-service-def456      Running   2
staging       web-frontend-ghi789     Running   0

💡 使用 get_container_metrics('namespace/pod-name') 查看详细指标
```

#### 2. 监控特定 Pod
```python
# 默认 namespace
get_container_metrics('xxx-service-abc123')

# 指定 namespace
get_container_metrics('production/api-service-def456')
```

**输出示例**:
```
=== 容器监控 ===

【运行环境】Kubernetes

【Pod 信息】production/api-service-def456
  状态: Running
  节点: node-1
  创建时间: 2026-05-28T10:00:00

【容器状态】
  • api-container ✅
    重启次数: 0

【资源使用】
  CPU: 250m
  内存: 512Mi

【健康评分】
✅ Pod 运行正常
```

#### 3. 查看 Pod 日志
```python
# 默认 namespace
get_container_logs('xxx-service-abc123', lines=200, since='2h')

# 指定 namespace
get_container_logs('production/api-service-def456', lines=500, since='24h')
```

---

## 告警集成

### 自动监控容器资源并告警

```python
# 创建定时任务，每 5 分钟检查一次
def monitor_container_resources():
    from service.tools.container_monitor_tool import get_container_metrics
    from service.tools.alert_tool import send_alert

    # 监控特定容器
    result = get_container_metrics('xxx-service')

    # 检查是否有问题
    if "⚠️" in result or "❌" in result:
        send_alert(
            title="容器 xxx-service 资源异常",
            message=result[:500],
            level="WARNING"
        )
```

### 监控容器重启

```python
def check_container_restarts():
    from service.tools.container_monitor_tool import get_container_metrics
    from service.tools.alert_tool import send_alert

    result = get_container_metrics('xxx-service')

    # 检查重启次数
    if "重启次数过多" in result:
        send_alert(
            title="容器 xxx-service 频繁重启",
            message=result,
            level="ERROR"
        )
```

---

## Agent 自主使用示例

**用户**: "xxx-service 容器运行正常吗？"
**Agent**: [调用 get_container_metrics('xxx-service')]

**用户**: "查看 xxx-service 的最近日志"
**Agent**: [调用 get_container_logs('xxx-service')]

**用户**: "生产环境的 api-service CPU 使用率怎么样？"
**Agent**: [调用 get_container_metrics('production/api-service')]

**用户**: "如果 xxx-service 的 CPU 超过 80% 就通知我"
**Agent**: [创建监控任务，定期检查并在超限时调用 send_alert()]

---

## 环境要求

### Docker 环境
- 需要安装 Docker
- 当前用户需要有 Docker 权限（或使用 sudo）
- 命令: `docker version` 可正常执行

### Kubernetes 环境
- 需要安装 kubectl
- 需要配置好 kubeconfig（~/.kube/config）
- 建议安装 metrics-server（用于获取资源使用情况）
- 命令: `kubectl version --client` 可正常执行

---

## 常见问题

### Q1: 提示"未检测到容器运行时"
**A**: 确保已安装 Docker 或 kubectl，并且命令可以正常执行。

### Q2: Kubernetes 无法获取资源指标
**A**: 需要在集群中安装 metrics-server:
```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

### Q3: Docker 提示权限不足
**A**: 将当前用户添加到 docker 组:
```bash
sudo usermod -aG docker $USER
# 重新登录生效
```

### Q4: 如何监控多个容器？
**A**: 可以创建定时任务，循环监控多个容器:
```python
containers = ['xxx-service', 'yyy-service', 'zzz-service']
for container in containers:
    result = get_container_metrics(container)
    # 处理结果...
```

---

## 工具总数更新

Lobster 现在拥有 **28 个工具**（26 → 28）:

- **基础工具**: 6 个
- **记忆工具**: 5 个
- **任务管理**: 6 个
- **代码执行**: 1 个
- **网络搜索**: 1 个
- **通知推送**: 1 个
- **系统监控**: 3 个
- **告警管理**: 2 个
- **诊断工具**: 1 个
- **容器监控**: 2 个 ✨ 新增

---

## 下一步优化

1. **支持更多容器平台**: Podman、containerd
2. **容器性能分析**: CPU/内存使用趋势图
3. **容器编排监控**: Docker Compose、Helm Release
4. **自动扩缩容建议**: 根据资源使用情况给出建议
5. **容器安全扫描**: 漏洞检测、镜像扫描
