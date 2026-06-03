"""
service/server.py — Lobster Agent HTTP API (FastAPI)

提供 REST 接口，供前端调用 Agent 回答用户问题。

端点：
  POST /api/ask   { "question": "..." }  → { "answer": "..." }
  GET  /health                           → { "status": "ok" }
"""

import logging
import os
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.responses import JSONResponse
import uvicorn
from service.agent import LobsterBrain
from config import settings

log = logging.getLogger("lobster.server")

# 延迟初始化 agent，避免在 import 时就加载模型
_agent = None
_agent_lock = threading.Lock()
_brain = None


def get_agent():
    global _agent
    with _agent_lock:
        if _agent is None:
            from smolagents import CodeAgent, LiteLLMModel
            from service.agent import get_prompt_templates
            from service.tools import (
                get_current_time, calculate, get_weather,
                get_investing_news, get_earnings_calendar, get_food_trends, get_tech_news,
                search_memory, remember_fact, recall_fact, list_all_facts, forget_fact,
                create_goal, list_active_goals, complete_goal, review_recent_reflections,
                create_task, list_tasks, delete_task, run_task_now, update_task,
                execute_python, search_web, send_notification,
                get_system_metrics, analyze_logs, send_alert, list_recent_alerts,
                check_database_health, run_diagnostics,
                get_container_metrics, get_container_logs,
            )

            model = LiteLLMModel(
                model_id=settings.agent.MODEL_ID,
                api_key=settings.agent.DEEPSEEK_API_KEY or os.environ.get("DEEPSEEK_API_KEY"),
                timeout=settings.agent.TIMEOUT,
                num_retries=settings.agent.NUM_RETRIES,
            )
            _agent = CodeAgent(
                tools=[
                    get_current_time, calculate, get_weather,
                    get_investing_news, get_earnings_calendar, get_food_trends, get_tech_news,
                    search_memory, remember_fact, recall_fact, list_all_facts, forget_fact,
                    create_goal, list_active_goals, complete_goal, review_recent_reflections,
                    create_task, list_tasks, delete_task, run_task_now, update_task,
                    execute_python, search_web, send_notification,
                    get_system_metrics, analyze_logs, send_alert, list_recent_alerts,
                    check_database_health, run_diagnostics,
                    get_container_metrics, get_container_logs,
                ],
                model=model,
                prompt_templates=get_prompt_templates(),
                additional_authorized_imports=["*"],
                max_steps=settings.agent.MAX_STEPS,
                verbosity_level=settings.agent.VERBOSITY_LEVEL,
            )
            log.info("Agent 初始化完成")
    return _agent


def get_brain():
    global _brain
    with _agent_lock:
        if _brain is None:
            _brain = LobsterBrain()
    return _brain


app = FastAPI(title="Lobster Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = ""


class AskResponse(BaseModel):
    answer: str


class ErrorResponse(BaseModel):
    error: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest):
    question = req.question.strip()
    if not question:
        return JSONResponse(status_code=400, content={"error": "question is required"})

    log.info("收到问题: %s", question)
    try:
        answer_str = get_brain().answer(question, get_agent().run, session_id="http")
        return {"answer": answer_str}
    except Exception as e:
        log.error("Agent 执行出错: %s", e)
        if "timeout" in str(e).lower():
            return JSONResponse(status_code=504, content={"error": "请求超时，请稍后重试"})
        return JSONResponse(status_code=500, content={"error": str(e)})


def start_server(host: str = None, port: int = None):
    host = host or settings.server.BACKEND_HOST
    port = port or settings.server.BACKEND_PORT
    log.info("🌐 Agent HTTP 服务启动: http://%s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="warning")
