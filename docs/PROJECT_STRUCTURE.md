# Lobster 项目结构

```
lobster/
├── main.py              # 项目入口（启动 Agent 服务 + 调度器）
├── requirements.txt     # Python 依赖
├── .env                 # 环境变量配置
├── .gitignore          # Git 忽略规则
│
├── docs/               # 📚 文档目录
│   ├── MEMORY_GUIDE.md              - 记忆系统使用指南
│   ├── MONITORING_GUIDE.md          - 监控告警使用指南
│   └── CONTAINER_MONITORING_GUIDE.md - 容器监控使用指南
│
├── scripts/            # 🛠️ 脚本工具
│   ├── query_db.py     - 数据库查询工具
│   └── start.sh        - 启动脚本
│
├── data/               # 💾 数据目录
│   ├── memory.db       - 记忆数据库（对话/知识库/目标/反思）
│   ├── tasks.db        - 任务数据库（定时任务配置）
│   └── alert_history.json - 告警历史记录
│
├── logs/               # 📝 日志目录
│   └── lobster.log     - 应用日志
│
├── service/            # 🧠 核心业务逻辑
│   ├── agent.py        - Agent 入口
│   ├── server.py       - HTTP API 服务
│   ├── scheduler.py    - 任务调度器
│   ├── db.py           - 任务数据库操作
│   ├── memory.py       - 记忆管理器
│   ├── brain.py        - Agent 大脑（上下文组装）
│   ├── agent_prompt.py - Agent 提示词模板
│   │
│   ├── tools/          # 工具集（28个）
│   │   ├── time_tool.py
│   │   ├── calculator_tool.py
│   │   ├── weather_tool.py
│   │   ├── investing_news_tool.py
│   │   ├── earnings_calendar_tool.py
│   │   ├── food_trends_tool.py
│   │   ├── memory_tool.py          - 记忆工具（5个）
│   │   ├── task_manager_tool.py    - 任务管理工具（5个）
│   │   ├── code_executor_tool.py
│   │   ├── web_search_tool.py
│   │   ├── notify_tool.py
│   │   ├── system_monitor_tool.py  - 系统监控
│   │   ├── log_analyzer_tool.py    - 日志分析
│   │   ├── alert_tool.py           - 智能告警
│   │   ├── database_health_tool.py - 数据库健康检查
│   │   ├── diagnostics_tool.py     - 一键诊断
│   │   └── container_monitor_tool.py - 容器监控
│   │
│   ├── reports/        # 📊 报告生成逻辑
│   │   ├── finance.py      - 财经简报
│   │   ├── earnings.py     - 财报日历
│   │   └── food_trends.py  - 餐饮趋势（含 AI 分析）
│   │
│   └── notifications/  # 📢 通知逻辑
│       ├── feishu.py   - 飞书推送
│       └── wxpusher.py - 微信推送
│
├── web/                # 🌐 前端（React + Vite）
│   ├── src/
│   ├── public/
│   └── package.json
│
└── tests/              # 🧪 测试
    └── ...
```

## 目录说明

### 核心文件
- **main.py**: 项目启动入口，同时启动 HTTP 服务和任务调度器
- **requirements.txt**: Python 依赖包列表

### docs/ - 文档
存放所有项目文档和使用指南，便于查阅

### scripts/ - 脚本工具
存放各种辅助脚本：
- `query_db.py`: 查询数据库数据的工具
- `start.sh`: 启动脚本

### data/ - 数据
存放所有运行时数据：
- `memory.db`: 记忆数据（对话、知识库、目标、反思、情景记忆）
- `tasks.db`: 定时任务配置和执行历史
- `alert_history.json`: 告警去重历史

### logs/ - 日志
存放应用日志文件，便于调试和问题排查

### service/ - 核心业务
- **tools/**: 28个工具，提供各种功能能力
- **reports/**: 报告生成逻辑（财经、财报、餐饮趋势）
- **notifications/**: 通知推送逻辑（飞书、微信）

## 使用方式

### 查询数据库
```bash
# 查看记忆数据库
python scripts/query_db.py memory

# 查看任务数据库
python scripts/query_db.py tasks

# 查看最近对话
python scripts/query_db.py conversations

# 查看知识库
python scripts/query_db.py knowledge
```

### 启动项目
```bash
# 启动服务（HTTP + 调度器）
python main.py

# 立即执行某个任务
python main.py --now finance
```

### 查看日志
```bash
tail -f logs/lobster.log
```
