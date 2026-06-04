# Lobster 项目结构

```
lobster/
├── main.py              # 项目入口（HTTP 服务 + 后台调度器）
├── requirements.txt     # Python 依赖
├── .env                 # 环境变量配置（不提交 Git）
├── .gitignore
│
├── config/             # ⚙️ 统一配置中心
│   └── settings.py     - 所有配置项（支持 .env 覆盖）；含 ServerSettings、
│                         AgentSettings、SchedulerSettings、MemorySettings、
│                         MonitorSettings、AlertSettings、ESSettings 等
│
├── docs/               # 📚 文档
│   ├── PROJECT_STRUCTURE.md         - 本文件
│   ├── ARCHITECTURE.md              - 系统架构说明
│   ├── MEMORY_GUIDE.md              - 记忆系统使用指南
│   ├── MONITORING_GUIDE.md          - 监控告警使用指南
│   └── CONTAINER_MONITORING_GUIDE.md - 容器监控使用指南
│
├── scripts/            # 🛠️ 辅助脚本
│   ├── query_db.py     - 数据库查询工具（memory / tasks / conversations）
│   ├── migrate_tasks.py - 任务数据库迁移
│   └── start.sh        - 一键启动脚本
│
├── data/               # 💾 运行时数据（不提交 Git）
│   ├── memory.db       - 记忆数据库（对话/事实/情景/反思/目标）
│   ├── tasks.db        - 定时任务数据库
│   └── alert_history.json - 告警去重历史
│
├── logs/               # 📝 日志（不提交 Git）
│   └── lobster.log     - 应用日志（按天轮转，保留 14 天）
│
├── service/            # 🧠 核心业务逻辑
│   ├── server.py       - FastAPI HTTP 服务
│   │                     POST /api/ask         → JSON 同步问答
│   │                     POST /api/ask/stream  → SSE 流式问答
│   │                     GET  /health          → 健康检查
│   ├── log_setup.py    - 日志初始化（stdout + 文件轮转）
│   │
│   ├── agent/          # 🤖 Agent 编排层
│   │   ├── __init__.py  - 对外导出 LobsterBrain、get_prompt_templates
│   │   ├── brain.py     - 认知编排（记忆注入、流式/非流式执行、经验落库）
│   │   │                  StreamEvent: plan | thought | code | observation | final | error
│   │   ├── prompt.py    - CodeAgent 系统提示词（追加 Lobster 专属规则）
│   │   └── runner.py    - 本地 CLI Agent 入口（交互模式 / 单次运行）
│   │
│   ├── memory/         # 🗄️ 多层记忆系统
│   │   ├── __init__.py
│   │   └── manager.py   - MemoryManager（SQLite 存储）
│   │                      短期：最近对话 | 语义：结构化事实
│   │                      情景：关键事件摘要 | 反思：执行经验
│   │                      目标：长期追踪目标
│   │
│   ├── scheduler/      # ⏰ 动态任务调度器
│   │   ├── __init__.py  - 对外导出 initialize_scheduler、run_scheduler_loop 等
│   │   ├── core.py      - 调度主循环（基于 schedule 库）
│   │   ├── db.py        - 任务 SQLite 存储（tasks.db）
│   │   └── handlers.py  - 任务执行器（内置任务 + 动态任务分发）
│   │
│   ├── tools/          # 🔧 Agent 工具集（注册到 CodeAgent）
│   │   ├── __init__.py  - 统一导出所有工具
│   │   │
│   │   ├── time_tool.py              - get_current_time
│   │   ├── calculator_tool.py        - calculate
│   │   ├── weather_tool.py           - get_weather（Open-Meteo）
│   │   ├── investing_news_tool.py    - get_investing_news（Investing RSS）
│   │   ├── earnings_calendar_tool.py - get_earnings_calendar（Nasdaq API）
│   │   ├── food_trends_tool.py       - get_food_trends（RSS 聚合）
│   │   ├── tech_news_tool.py         - get_tech_news（科技资讯 RSS）
│   │   ├── web_search_tool.py        - search_web（Tavily API）
│   │   ├── code_executor_tool.py     - execute_python（沙箱执行）
│   │   ├── notify_tool.py            - send_notification（微信/飞书）
│   │   │
│   │   ├── memory_tool.py            - search_memory / remember_fact /
│   │   │                               recall_fact / list_all_facts / forget_fact
│   │   ├── task_manager_tool.py      - create_task / list_tasks / delete_task /
│   │   │                               run_task_now / update_task
│   │   ├── scheduled_tasks_tool.py   - 定时任务调度相关工具
│   │   │
│   │   ├── system_monitor_tool.py    - get_system_metrics（CPU/内存/磁盘）
│   │   ├── log_analyzer_tool.py      - analyze_logs（本地日志分析）
│   │   ├── es_log_monitor_tool.py    - ES 日志查询与监控
│   │   ├── alert_tool.py             - send_alert / list_recent_alerts（去重告警）
│   │   ├── database_health_tool.py   - check_database_health
│   │   ├── diagnostics_tool.py       - run_diagnostics（一键诊断）
│   │   └── container_monitor_tool.py - get_container_metrics / get_container_logs
│   │
│   ├── reports/        # 📊 定时报告生成
│   │   ├── __init__.py
│   │   ├── finance.py      - 财经简报（复用 investing_news_tool）
│   │   ├── earnings.py     - 财报日历（复用 earnings_calendar_tool）
│   │   ├── food_trends.py  - 餐饮趋势（复用 food_trends_tool）
│   │   ├── tech_news.py    - 科技资讯（复用 tech_news_tool）
│   │   └── log_monitor.py  - 日志异常巡检报告
│   │
│   └── notifications/  # 📢 消息推送
│       ├── __init__.py
│       ├── wxpusher.py - 微信推送（WxPusher）
│       └── feishu.py   - 飞书 Webhook 推送
│
├── web/                # 🌐 前端（React + TypeScript + Vite）
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts  - /api 代理到 localhost:8765
│   └── src/
│       ├── main.tsx
│       ├── App.tsx     - 路由根组件；SSE 流式消费逻辑；Message / ThinkingStep 类型
│       ├── App.css     - 全局样式（暗色主题、思考动画、打字机光标）
│       └── components/
│           ├── ChatWindow.tsx   - 消息列表容器（自动滚底）
│           ├── InputBar.tsx     - 输入框（Enter 发送 / Shift+Enter 换行）
│           └── MessageBubble.tsx - 消息气泡；思考步骤折叠区；打字机动画
│
└── tests/              # 🧪 单元测试
    ├── test_brain.py          - LobsterBrain 测试
    ├── test_memory.py         - MemoryManager 测试
    ├── test_dynamic_tasks.py  - 动态任务调度测试
    └── test_web_search_tool.py - Web 搜索工具测试
```

## 核心模块说明

### `main.py` — 启动入口
- 加载 `.env`，初始化日志
- 后台线程启动调度器（`service/scheduler`）
- 主线程启动 FastAPI HTTP 服务（`service/server.py`，默认端口 8765）
- `--now <task>` 参数可立即执行指定任务（finance / food / earnings / all / 任意已创建任务名）

### `config/settings.py` — 配置中心
所有可配置项集中在此，支持通过 `.env` 环境变量覆盖。主要分组：
`ServerSettings` · `AgentSettings` · `SchedulerSettings` · `MemorySettings` · `MonitorSettings` · `AlertSettings` · `ESSettings` · `LogSettings`

### `service/agent/` — 认知编排
- **`brain.py`**：`LobsterBrain.answer()` 同步执行；`answer_stream()` 流式执行，逐步 yield `StreamEvent`；每轮完成后自动落库（对话、反思、情景记忆、目标状态）
- **`prompt.py`**：在 smolagents 默认 `code_agent.yaml` 末尾追加 Lobster 专属规则（格式约束 + 业务能力说明）
- **`runner.py`**：CLI 入口，与 `server.py` 共享同一套 `CodeAgent` + 工具列表

### `service/server.py` — HTTP API
| 端点 | 说明 |
|------|------|
| `POST /api/ask` | 同步问答，返回 `{ "answer": "..." }` |
| `POST /api/ask/stream` | SSE 流式问答，依次推送 `ready / plan / thought / code / observation / final / error / done` 事件 |
| `GET /health` | 健康检查 |

Agent 和 Brain 均延迟初始化（`get_agent()` / `get_brain()`），不在 import 时加载模型。

### `service/memory/` — 多层记忆
基于 SQLite，提供五类记忆：短期对话 → 语义事实 → 情景摘要 → 经验反思 → 长期目标。每轮 `brain.answer()` 自动读写。

### `service/scheduler/` — 动态调度
- `core.py`：主循环每 30s 扫描一次，触发到期任务
- `db.py`：任务 CRUD（`tasks.db`），记录上次运行时间和状态
- `handlers.py`：内置任务（finance/food/earnings/tech_news/log_monitor）+ 动态任务（由 `task_manager_tool` 创建，执行用户自定义 Python 代码）

### `web/src/` — 前端
- **`App.tsx`**：用 `fetch` + `ReadableStream` 手动消费 SSE（原生 `EventSource` 不支持 POST）；收集 `ThinkingStep[]`；收到 `final` 事件时触发打字机动画
- **`MessageBubble.tsx`**：`useTypewriter` hook（~360 字/秒）；`ThinkingSteps` 折叠组件（加载中展开，打字完成 1.2s 后自动折叠）

## 数据流

```
用户 → InputBar
     → App.handleSend (fetch POST /api/ask/stream)
     → server.ask_stream → brain.answer_stream → agent.run(stream=True)
     ← SSE: ready / plan / thought / code / observation / final / done
     ← MessageBubble: 实时更新思考步骤 → 打字机展示最终答案
```

## 常用命令

```bash
# 启动完整服务（后端 + 调度器）
python main.py

# 指定端口
python main.py --port 8765

# 立即执行内置任务（调试用）
python main.py --now finance
python main.py --now food
python main.py --now earnings
python main.py --now all

# 本地 CLI Agent（不启动 HTTP 服务）
python service/agent/runner.py "香港明天天气如何？"

# 前端开发服务器（代理到 8765）
cd web && npm run dev

# 前端构建
cd web && npm run build

# 运行测试
python -m unittest discover -s tests -v

# 查询数据库
python scripts/query_db.py memory
python scripts/query_db.py tasks
python scripts/query_db.py conversations

# 实时查看日志
tail -f logs/lobster.log
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek API 密钥 |
| `TAVILY_API_KEY` | ✅ | Tavily 搜索 API 密钥 |
| `WXPUSHER_APP_TOKEN` | 推送用 | WxPusher 应用 Token |
| `WXPUSHER_UID` | 推送用 | WxPusher 用户 UID |
| `FEISHU_WEBHOOK` | 推送用 | 飞书机器人 Webhook URL |
| `AGENT_MODEL_ID` | 可选 | 模型 ID（默认 `deepseek/deepseek-reasoner`） |
| `BACKEND_PORT` | 可选 | 后端端口（默认 `8765`） |
| `ES_BASE_URL` | 可选 | Elasticsearch 地址（默认 `http://localhost:9200`） |

