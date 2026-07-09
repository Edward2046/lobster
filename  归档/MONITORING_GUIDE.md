# 监控工具使用指南

## 概述

Lobster 现已集成完整的监控告警体系，包含 6 个高优先级监控工具，帮助及时发现和解决系统问题。

## 工具列表

### 1. get_system_metrics() - 系统资源监控
**用途**: 实时监控 CPU、内存、磁盘使用情况

**使用场景**:
- 定期健康检查
- 性能问题排查
- 资源预警

**示例**:
```python
get_system_metrics()
```

**输出内容**:
- CPU 使用率和负载
- 内存使用情况
- 磁盘空间（根目录和数据库目录）
- 当前进程资源占用
- 健康评分和问题提示

---

### 2. analyze_logs() - 日志分析
**用途**: 分析应用日志，快速定位错误和异常

**参数**:
- `log_file`: 日志文件路径（默认: "lobster.log"）
- `hours`: 分析最近 N 小时的日志（默认: 24）
- `keyword`: 关键词过滤（可选）
- `error_only`: 只显示错误日志（默认: False）

**使用场景**:
- 排查最近的错误
- 统计错误类型和频率
- 搜索特定问题

**示例**:
```python
# 分析最近 24 小时的所有日志
analyze_logs()

# 只看错误日志
analyze_logs(error_only=True)

# 搜索包含 "timeout" 的日志
analyze_logs(keyword="timeout", hours=12)
```

**输出内容**:
- 日志级别统计（ERROR/WARNING/INFO）
- 错误类型 Top 5
- 最近的错误和警告日志
- 健康评估和建议

---

### 3. send_alert() - 智能告警
**用途**: 发送分级告警，自动去重，智能选择通知渠道

**参数**:
- `title`: 告警标题
- `message`: 详细消息
- `level`: 告警级别（INFO/WARNING/ERROR/CRITICAL）
- `dedupe_minutes`: 去重时间窗口（默认: 60 分钟）

**告警级别与通道**:
- `INFO` / `WARNING` → 飞书
- `ERROR` → 飞书 + 微信
- `CRITICAL` → 飞书 + 微信 + 邮件

**使用场景**:
- 系统异常自动告警
- 资源超限通知
- 任务失败提醒

**示例**:
```python
# 发送警告
send_alert(
    title="CPU 使用率过高",
    message="当前 CPU 使用率 85%，持续 5 分钟",
    level="WARNING"
)

# 发送严重告警
send_alert(
    title="数据库连接失败",
    message="无法连接到 memory.db，请立即检查",
    level="CRITICAL"
)
```

**特性**:
- ✅ 自动去重（同一告警 1 小时内只发送一次）
- ✅ 分级通知（根据严重程度选择渠道）
- ✅ 告警历史记录

---

### 4. list_recent_alerts() - 告警历史
**用途**: 查看最近发送的告警记录

**参数**:
- `hours`: 查看最近 N 小时的告警（默认: 24）

**示例**:
```python
list_recent_alerts(hours=24)
```

---

### 5. check_database_health() - 数据库健康检查
**用途**: 检查 SQLite 数据库状态，可选自动清理旧数据

**参数**:
- `db_path`: 数据库文件路径（默认: "memory.db"）
- `cleanup_days`: 清理 N 天前的旧数据（默认: 0，不清理）

**使用场景**:
- 定期数据库维护
- 性能问题排查
- 自动清理过期数据

**示例**:
```python
# 只检查，不清理
check_database_health()

# 检查并清理 30 天前的数据
check_database_health(cleanup_days=30)
```

**输出内容**:
- 数据库文件大小
- 各表记录数统计
- 索引状态
- 完整性检查
- 查询性能测试
- 优化建议

---

### 6. run_diagnostics() - 一键诊断 🔥
**用途**: 运行所有监控工具，生成综合诊断报告

**参数**:
- `include_cleanup`: 是否自动清理旧数据（默认: False）

**使用场景**:
- 每日健康检查
- 问题全面排查
- 系统巡检

**示例**:
```python
# 只诊断，不清理
run_diagnostics()

# 诊断并自动清理
run_diagnostics(include_cleanup=True)
```

**诊断内容**:
1. 系统资源监控（CPU、内存、磁盘）
2. 日志分析（最近 24 小时）
3. 数据库健康检查
4. 网络连通性检查（DeepSeek API、RSS 源等）
5. 综合健康评分
6. 自动修复建议

---

## 推荐使用方式

### 1. 定时健康检查（每天早上 8 点）
```python
# 在 main.py 的调度器中添加
def daily_health_check():
    from service.tools.diagnostics_tool import run_diagnostics
    from service.tools.alert_tool import send_alert

    report = run_diagnostics()

    # 如果发现问题，发送告警
    if "⚠️" in report or "❌" in report:
        send_alert(
            title="每日健康检查发现问题",
            message=report[:500],  # 截取前 500 字符
            level="WARNING"
        )
```

### 2. 资源监控告警（每 5 分钟）
```python
def check_resources():
    from service.tools.system_monitor_tool import get_system_metrics
    from service.tools.alert_tool import send_alert
    import psutil

    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory().percent

    if cpu > 80:
        send_alert(
            title="CPU 使用率过高",
            message=f"当前 CPU 使用率: {cpu}%",
            level="WARNING"
        )

    if mem > 85:
        send_alert(
            title="内存使用率过高",
            message=f"当前内存使用率: {mem}%",
            level="WARNING"
        )
```

### 3. 错误日志监控（每小时）
```python
def check_error_logs():
    from service.tools.log_analyzer_tool import analyze_logs
    from service.tools.alert_tool import send_alert

    report = analyze_logs(hours=1, error_only=True)

    # 如果最近 1 小时有错误
    if "ERROR" in report and "0 条" not in report:
        send_alert(
            title="检测到错误日志",
            message=report[:500],
            level="ERROR"
        )
```

### 4. 数据库维护（每周日凌晨 2 点）
```python
def weekly_db_maintenance():
    from service.tools.database_health_tool import check_database_health
    from service.tools.alert_tool import send_alert

    # 清理 30 天前的旧数据
    report = check_database_health(cleanup_days=30)

    send_alert(
        title="数据库周维护完成",
        message=report,
        level="INFO"
    )
```

---

## Agent 自主使用示例

Agent 现在可以主动使用这些工具：

**用户**: "系统运行正常吗？"
**Agent**: [调用 run_diagnostics() 进行全面检查]

**用户**: "最近有什么错误吗？"
**Agent**: [调用 analyze_logs(error_only=True) 查看错误日志]

**用户**: "CPU 使用率怎么样？"
**Agent**: [调用 get_system_metrics() 查看系统资源]

**用户**: "数据库有多大了？"
**Agent**: [调用 check_database_health() 查看数据库状态]

**用户**: "如果 CPU 超过 80% 就通知我"
**Agent**: [调用 create_task() 创建监控任务，超限时调用 send_alert()]

---

## 工具总览

Lobster 现在拥有 **26 个工具**：

- **基础工具**: 6 个（时间、计算、天气、财经、财报、餐饮）
- **记忆工具**: 5 个（搜索、记住、回忆、列表、忘记）
- **任务管理**: 6 个（创建、列表、删除、执行、更新、统计）
- **代码执行**: 1 个
- **网络搜索**: 1 个
- **通知推送**: 1 个
- **系统监控**: 3 个 ✨ 新增
- **告警管理**: 2 个 ✨ 新增
- **诊断工具**: 1 个 ✨ 新增

---

## 下一步优化建议

1. **集成到调度器**: 在 `main.py` 中添加定时监控任务
2. **配置告警阈值**: 在 `.env` 中配置 CPU/内存/磁盘告警阈值
3. **邮件通知**: 实现 `send_email` 工具，用于 CRITICAL 级别告警
4. **监控面板**: 考虑添加 Web 监控面板，可视化展示系统状态
5. **历史趋势**: 记录监控指标历史，分析趋势和异常
