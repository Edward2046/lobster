# 🦞 Lobster Agent

Lobster 是一个**本地运行的智能 AI Agent**，基于 [smolagents](https://github.com/huggingface/smolagents) 的 CodeAgent 架构（模型通过「写 Python 代码」的方式调用工具），默认接入 DeepSeek 模型。它既能像聊天助手一样回答问题，也内置了**定时任务调度器**、**多层记忆**、**系统/日志监控**和**消息推送**能力，并配有一个 Gemini 风格的 Web 前端。

---

## ✨ 功能特性

- **对话式问答**：天气、财经资讯、财报日历、餐饮趋势、科技新闻、联网搜索、数学计算等。
- **代码执行**：Agent 可编写并直接运行 Python 代码来完成任意任务。
- **定时任务**：用自然语言描述需求，Agent 自动生成代码、设定调度、常驻运行（基于 SQLite，无需系统 crontab）。支持创建 / 列出 / 修改 / 删除 / 暂停恢复 / 立即执行。
- **多层记忆**：情景记忆、长期事实/偏好、目标追踪、执行反思，跨会话保持连续性（可选向量检索）。
- **运维诊断**：系统资源监控（CPU/内存/磁盘）、日志分析、数据库健康检查、容器监控、Elasticsearch 错误日志监控与突增告警。
- **消息推送**：执行结果可通过 **微信（WxPusher）** 或 **飞书 Webhook** 推送。
- **流式前端**：React + Vite 单页应用，SSE 实时展示「思考过程 → 最终答案」，Markdown 渲染、打字机效果。
- **健壮性兜底**：自动修复模型生成的坏代码（未闭合字符串、缺失 import），单步错误自愈重试而不丢失答案。

---

## 🏗️ 技术栈与架构

```
┌─────────────┐   自然语言    ┌──────────────────┐   写代码调用   ┌──────────────┐
│  Web 前端   │ ───SSE────► │  LobsterBrain    │ ──────────► │   工具集      │
│ React+Vite  │ ◄─────────  │  + CodeAgent     │             │  service/tools│
└─────────────┘   流式回答   │  (smolagents)    │             └──────────────┘
                            └────────┬─────────┘                     │
                                     │ LiteLLM                       │
                            ┌────────▼─────────┐            ┌────────▼────────┐
                            │  DeepSeek 模型    │            │ 调度器/记忆/通知 │
                            └──────────────────┘            │  SQLite 持久化   │
                                                            └─────────────────┘
```

- **后端**：Python + FastAPI + smolagents（LiteLLM 适配 DeepSeek）+ `schedule` 调度库 + SQLite。
- **前端**：React 18 + TypeScript + Vite + react-markdown。
- **入口**：`main.py` 同时启动 Agent HTTP 服务（主线程）和调度器（后台线程）。

### 目录结构

```
lobster/
├── main.py                # 项目入口：Agent 服务 + 调度器
├── config/                # 统一配置中心（从 .env 读取）
├── service/
│   ├── agent/             # 认知编排（brain）、CodeAgent、提示词
│   ├── tools/             # 所有 Agent 工具
│   ├── scheduler/         # 动态任务调度 + SQLite
│   ├── memory/            # 多层记忆管理
│   ├── notifications/     # WxPusher / 飞书推送
│   └── server.py          # FastAPI HTTP + SSE 接口
├── web/                   # React + Vite 前端
├── scripts/               # start.sh 等运维脚本
├── tests/                 # 单元测试
└── data/ | logs/          # SQLite 数据 / 日志（运行时生成）
```

---

## 🚀 快速开始

### 环境要求

- Python **3.10+**（代码使用了 `str | None` 等新语法）
- Node.js **18+**（前端）
- 一个 **DeepSeek API Key**（[申请地址](https://platform.deepseek.com/)）

### 1. 克隆并配置

```bash
git clone <your-repo-url> lobster
cd lobster

# 复制环境变量模板并填入你的真实配置
cp .env.example .env
# 编辑 .env，至少填入 DEEPSEEK_API_KEY
```

### 2. 安装后端依赖

```bash
python3 -m venv .venv && source .venv/bin/activate   # 可选：虚拟环境
pip install -r requirements.txt
```

### 3. 安装前端依赖

```bash
cd web && npm install && cd ..
```

### 4. 启动

一键启动前后端（推荐）：

```bash
./scripts/start.sh start     # 启动后端(:8765) + 前端(:5173)
./scripts/start.sh stop      # 停止
```

启动后打开浏览器访问 **http://localhost:5173**。

---

## 📦 部署与运行方式

### 方式一：脚本托管（推荐）

`scripts/start.sh` 会用 `nohup` 后台拉起前后端、写 PID 文件、做健康检查，日志落在 `logs/` 下：

```bash
./scripts/start.sh start   # 后台启动
./scripts/start.sh stop    # 停止
# 日志：logs/backend.log、logs/frontend.log、logs/lobster.log
```

### 方式二：手动分别启动

```bash
# 后端（含调度器）
python main.py                 # 默认端口 8765
python main.py --port 9000     # 指定端口

# 前端（开发模式）
cd web && npm run dev -- --host 0.0.0.0

# 前端（生产构建）
cd web && npm run build        # 产物在 web/dist，可用任意静态服务器托管
```

### 方式三：手动触发任务（测试/调试）

```bash
python main.py --now all        # 立即执行全部内置任务
python main.py --now finance    # 财经简报
python main.py --now earnings   # 财报日历
python main.py --now <任务名>    # 任意已创建的任务
```

### 保持不休眠（macOS）

若部署在 MacBook 上、希望合盖或空闲时后端不被系统挂起：

```bash
caffeinate -is ./scripts/start.sh start
```

---

## ⚙️ 配置说明

所有配置集中在 `config/settings.py`，均可通过 `.env` 覆盖。完整清单见 [`.env.example`](./.env.example)，最关键的几项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key（**必填**） | — |
| `AGENT_MODEL_ID` | 主模型 | `deepseek/deepseek-reasoner` |
| `AGENT_MODEL_ID_FAST` | 简单意图用的轻量模型 | `deepseek/deepseek-chat` |
| `BACKEND_PORT` | 后端端口 | `8765` |
| `FRONTEND_PORT` | 前端端口 | `5173` |
| `WXPUSHER_APP_TOKEN` / `WXPUSHER_UIDS` | 微信推送（可选） | — |
| `FEISHU_WEBHOOK` | 飞书群机器人 Webhook（可选） | — |
| `TAVILY_API_KEY` | 联网搜索（可选） | — |

> ⚠️ 真实密钥只放进 `.env`（已被 `.gitignore` 忽略），**不要**提交到仓库。

---

## 🔌 HTTP 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/api/ask` | 同步问答，body: `{"question": "..."}` → `{"answer": "..."}` |
| `POST` | `/api/ask/stream` | SSE 流式问答，逐步推送 `plan/thought/code/observation/final` 等事件 |

---

## 🧰 内置工具（节选）

时间 / 计算 / 天气 / 财经资讯 / 财报日历 / 餐饮趋势 / 科技新闻 / 联网搜索、
记忆与目标（`remember_fact` / `recall_fact` / `create_goal` …）、
定时任务（`create_task` / `list_tasks` / `update_task` / `run_task_now` / `delete_task`）、
代码执行（`execute_python`）、通知（`send_notification`）、
运维监控（`get_system_metrics` / `analyze_logs` / `check_database_health` / `run_diagnostics` / `get_container_metrics` / 容器与 ES 日志监控）等。

---

## 🧪 测试

```bash
python -m unittest discover -s tests -v
```

---

## 📄 许可证

内部/个人项目，按需补充。
