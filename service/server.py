"""
service/server.py — Lobster Agent HTTP API

提供 REST 接口，供前端调用 Agent 回答用户问题。

端点：
  POST /api/ask   { "question": "..." }  → { "answer": "..." }
  GET  /health                           → { "status": "ok" }
"""

import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("lobster.server")

# 延迟初始化 agent，避免在 import 时就加载模型
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        from smolagents import CodeAgent, LiteLLMModel
        from service.tools import (
            get_current_time, calculate, get_weather,
            get_investing_news, get_earnings_calendar, get_food_trends,
            get_scheduled_task_count,
        )

        model = LiteLLMModel(
            model_id="deepseek/deepseek-reasoner",
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            timeout=30,
            num_retries=0,
        )
        _agent = CodeAgent(
            tools=[get_current_time, calculate, get_weather,
                   get_investing_news, get_earnings_calendar, get_food_trends,
                   get_scheduled_task_count],
            model=model,
            max_steps=5,
            verbosity_level=0,
        )
        log.info("Agent 初始化完成")
    return _agent


class AgentHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.info(fmt, *args)

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/ask":
            self._send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._send_json(400, {"error": "invalid JSON"})
            return

        question = (body.get("question") or "").strip()
        if not question:
            self._send_json(400, {"error": "question is required"})
            return

        log.info("收到问题: %s", question)
        try:
            answer = get_agent().run(question)
            self._send_json(200, {"answer": str(answer)})
        except Exception as e:
            log.error("Agent 执行出错: %s", e)
            self._send_json(500, {"error": str(e)})


def start_server(host: str = "0.0.0.0", port: int = 8765):
    server = ThreadingHTTPServer((host, port), AgentHandler)
    log.info("🌐 Agent HTTP 服务启动: http://%s:%d", host, port)
    server.serve_forever()
