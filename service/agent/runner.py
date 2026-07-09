"""
agent.py — 本地 AI Agent 入口

架构概览：
  ┌─────────────┐   自然语言问题    ┌──────────────────┐
  │    用户      │ ──────────────► │   CodeAgent      │
  └─────────────┘                 │  (smolagents)    │
                                  │                  │
                                  │  1. 思考(Thought) │
                                  │  2. 写代码(Code)  │
                                  │  3. 执行工具      │
                                  │  4. 观察结果      │
                                  │  5. 重复直到完成  │
                                  └────────┬─────────┘
                                           │ 调用工具
                                  ┌────────▼─────────┐
                                  │  tools/          │
                                  │  - get_current_time
                                  │  - calculate     │
                                  │  - get_weather   │
                                  └────────┬─────────┘
                                           │ LiteLLM 转发
                                  ┌────────▼─────────┐
                                  │  Ollama (本地)    │
                                  │  qwen2:7b        │
                                  └──────────────────┘

使用方式：
    python agent.py                          # 交互模式，持续对话
    python agent.py "东京现在几点？"           # 单次提问后退出
"""

import sys
import os
from dotenv import load_dotenv
from smolagents import LiteLLMModel
from service.agent.brain import LobsterBrain
from service.agent.code_agent import LobsterCodeAgent
from service.agent.prompt import get_prompt_templates
from service.tools import (
    get_current_time,
    calculate,
    get_weather,
    get_investing_news,
    get_earnings_calendar,
    get_food_trends,
    search_memory,
    remember_fact,
    recall_fact,
    list_all_facts,
    forget_fact,
    create_goal,
    list_active_goals,
    complete_goal,
    review_recent_reflections,
    create_task,
    list_tasks,
    delete_task,
    run_task_now,
    update_task,
    execute_python,
    search_web,
    send_notification,
    get_system_metrics,
    analyze_logs,
    send_alert,
    list_recent_alerts,
    check_database_health,
    run_diagnostics,
    get_container_metrics,
    get_container_logs,
)

# 从 .env 文件加载环境变量（DEEPSEEK_API_KEY 等）
load_dotenv()


# ── 模型配置 ──────────────────────────────────────────────────────────────────
# 使用 DeepSeek API，通过 LiteLLM 适配。
# API key 从 .env 文件读取，不硬编码在代码里。
# DeepSeek 兼容 OpenAI 接口，model_id 格式：deepseek/<模型名>
MODEL_ID = "deepseek/deepseek-v4-flash"  # deepseek-chat = DeepSeek-V3，速度快、能力强

model = LiteLLMModel(
    model_id=MODEL_ID,
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
)


# ── Agent 配置 ────────────────────────────────────────────────────────────────
# CodeAgent 是 smolagents 的核心 Agent 类型。
# 它让模型以"写 Python 代码"的方式来调用工具，而不是直接输出 JSON。
# 这样做的好处：模型可以用代码组合多个工具、做条件判断、处理中间结果。
#
# 参数说明：
#   tools         — 注册给 Agent 的工具列表，Agent 只能调用这里列出的工具
#   model         — 驱动 Agent 推理的语言模型
#   max_steps     — 最多执行几轮 Thought→Code→Observation 循环，防止死循环
#   verbosity_level — 日志详细程度：0=静默，1=显示每步摘要，2=显示完整代码
agent = LobsterCodeAgent(
    tools=[
        get_current_time,
        calculate,
        get_weather,
        get_investing_news,
        get_earnings_calendar,
        get_food_trends,
        search_memory,
        remember_fact,
        recall_fact,
        list_all_facts,
        forget_fact,
        create_goal,
        list_active_goals,
        complete_goal,
        review_recent_reflections,
        create_task,
        list_tasks,
        delete_task,
        run_task_now,
        update_task,
        execute_python,
        search_web,
        send_notification,
        get_system_metrics,
        analyze_logs,
        send_alert,
        list_recent_alerts,
        check_database_health,
        run_diagnostics,
        get_container_metrics,
        get_container_logs,
    ],
    model=model,
    prompt_templates=get_prompt_templates(),
    additional_authorized_imports=["*"],
    max_steps=15,
    verbosity_level=1,
)

brain = LobsterBrain()


# ── 单次运行 ──────────────────────────────────────────────────────────────────

def run_once(question: str) -> None:
    """向 Agent 提一个问题，打印结果后返回。"""
    print(f"\nQuestion: {question}")
    print("-" * 40)
    answer = brain.answer(question, agent.run, session_id="cli")
    print("-" * 40)
    print(f"Answer: {answer}\n")


# ── 交互模式 ──────────────────────────────────────────────────────────────────

def interactive() -> None:
    """启动一个持续的命令行对话循环。"""
    print("Local AI Agent (smolagents + Ollama)")
    print(f"Model: {MODEL_ID}")
    print("Type 'quit' or 'exit' to stop.\n")
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+D（EOF）或 Ctrl+C 时优雅退出，不打印异常堆栈
            print("\nBye!")
            break
        if not question:
            # 用户直接按回车，忽略空输入
            continue
        if question.lower() in ("quit", "exit"):
            print("Bye!")
            break
        run_once(question)


# ── 程序入口 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 有命令行参数时：把所有参数拼成一个问题，单次运行后退出
        # 例：python agent.py what time is it in Tokyo
        run_once(" ".join(sys.argv[1:]))
    else:
        # 无参数时：进入交互模式
        interactive()
