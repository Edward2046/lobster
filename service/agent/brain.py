"""
brain.py — Lobster 的轻量认知编排层

负责：
  1. 基于多层记忆构建上下文
  2. 为每轮请求注入意图、计划与成功标准
  3. 在执行后保存情景记忆、反思和目标状态
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable, Iterator, Optional

from service.memory.manager import MemoryManager, get_memory_manager

log = logging.getLogger("lobster.brain")

# smolagents 解析失败时错误信息里包含的原始文本片段
_PARSE_ERROR_SNIPPET_RE = re.compile(
    r"Here is your code snippet:\s*([\s\S]+)", re.DOTALL
)


def _extract_text_from_parse_error(exc: Exception) -> str | None:
    """从 AgentParsingError 中抽取模型原始输出的文本（去掉游离的 </code> 等标签）。"""
    msg = str(exc)
    m = _PARSE_ERROR_SNIPPET_RE.search(msg)
    if not m:
        return None
    raw = m.group(1).strip()
    # 去掉模型误放的游离标签
    raw = re.sub(r"^\s*</?code>\s*", "", raw)
    raw = re.sub(r"\s*</?code>\s*$", "", raw)
    return raw.strip() or None


Runner = Callable[[str], object]
StreamRunner = Callable[[str], Iterator[object]]


@dataclass
class PreparedTurn:
    prompt: str
    intent: str
    success_criteria: list[str]
    tracked_goal: str | None


@dataclass
class StreamEvent:
    """流式事件，给 server 层转 SSE 用。"""
    kind: str       # "plan" | "thought" | "code" | "observation" | "final" | "error"
    text: str
    step: int = 0   # ActionStep 的 step_number，PlanningStep 也算一步


class LobsterBrain:
    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        self.memory = memory_manager or get_memory_manager()

    def answer(self, question: str, runner: Runner, *, session_id: str | None = None) -> str:
        prepared = self.prepare(question)
        try:
            answer = str(runner(prepared.prompt))
        except Exception as exc:
            # 兜底：如果是 CodeAgent 格式解析错误（AgentParsingError），
            # 尝试从错误信息里提取模型原始输出文本，避免把有效答案当错误抛出。
            recovered = _extract_text_from_parse_error(exc)
            if recovered:
                log.warning("CodeAgent 格式解析失败，已从错误信息中恢复原始文本: %s", exc)
                answer = recovered
            else:
                self.memory.save_conversation(role="user", content=question, session_id=session_id)
                self.memory.save_reflection(
                    question,
                    answer_summary="执行失败",
                    outcome="failure",
                    lessons=f"本轮失败原因：{exc}",
                    confidence=1.0,
                )
                self.memory.remember_episode(
                    summary=f"失败：{self._trim(question, 80)}",
                    details=f"问题：{question}\n错误：{exc}",
                    tags=[prepared.intent, "failure"],
                    importance=0.8,
                    session_id=session_id,
                )
                if prepared.tracked_goal:
                    self.memory.update_goal_status(prepared.tracked_goal, "blocked")
                raise

        self.memory.save_conversation(role="user", content=question, session_id=session_id)
        self.memory.save_conversation(role="agent", content=answer, session_id=session_id)
        self.memory.save_reflection(
            question,
            answer_summary=self._trim(answer, 180),
            outcome="success",
            lessons=self._derive_lesson(prepared.intent, answer),
            confidence=0.75,
        )
        self.memory.remember_episode(
            summary=self._build_episode_summary(question, answer),
            details=f"问题：{question}\n回答：{self._trim(answer, 600)}",
            tags=[prepared.intent, "success"],
            importance=self._estimate_importance(question),
            session_id=session_id,
        )
        if prepared.tracked_goal:
            self.memory.update_goal_status(prepared.tracked_goal, "completed")
        return answer

    def answer_stream(
        self,
        question: str,
        stream_runner: StreamRunner,
        *,
        session_id: str | None = None,
    ) -> Iterator[StreamEvent]:
        """流式回答，逐步 yield StreamEvent。

        stream_runner(prompt) 应返回一个迭代器，元素来自 smolagents
        agent.run(stream=True)：ActionStep / PlanningStep / FinalAnswerStep。
        """
        prepared = self.prepare(question)
        final_answer: str = ""
        had_error: Optional[Exception] = None

        try:
            for raw_step in stream_runner(prepared.prompt):
                for event in self._adapt_step(raw_step):
                    if event.kind == "final":
                        final_answer = event.text
                    yield event
        except Exception as exc:
            # 兜底：AgentParsingError 时尝试恢复原始文本作为最终答案
            recovered = _extract_text_from_parse_error(exc)
            if recovered:
                log.warning("CodeAgent 流式格式解析失败，已恢复原始文本: %s", exc)
                final_answer = recovered
                yield StreamEvent(kind="final", text=recovered)
            else:
                had_error = exc
                yield StreamEvent(kind="error", text=str(exc))

        # 不论成功失败都要落库（与 answer 行为对齐）
        if had_error is not None:
            self.memory.save_conversation(role="user", content=question, session_id=session_id)
            self.memory.save_reflection(
                question,
                answer_summary="执行失败",
                outcome="failure",
                lessons=f"本轮失败原因：{had_error}",
                confidence=1.0,
            )
            self.memory.remember_episode(
                summary=f"失败：{self._trim(question, 80)}",
                details=f"问题：{question}\n错误：{had_error}",
                tags=[prepared.intent, "failure"],
                importance=0.8,
                session_id=session_id,
            )
            if prepared.tracked_goal:
                self.memory.update_goal_status(prepared.tracked_goal, "blocked")
            return

        # success
        self.memory.save_conversation(role="user", content=question, session_id=session_id)
        self.memory.save_conversation(role="agent", content=final_answer, session_id=session_id)
        self.memory.save_reflection(
            question,
            answer_summary=self._trim(final_answer, 180),
            outcome="success",
            lessons=self._derive_lesson(prepared.intent, final_answer),
            confidence=0.75,
        )
        self.memory.remember_episode(
            summary=self._build_episode_summary(question, final_answer),
            details=f"问题：{question}\n回答：{self._trim(final_answer, 600)}",
            tags=[prepared.intent, "success"],
            importance=self._estimate_importance(question),
            session_id=session_id,
        )
        if prepared.tracked_goal:
            self.memory.update_goal_status(prepared.tracked_goal, "completed")

    def _adapt_step(self, raw_step) -> Iterator[StreamEvent]:
        """把 smolagents 的原始 step 转成 StreamEvent 序列。"""
        cls_name = type(raw_step).__name__

        if cls_name == "ActionStep":
            step_no = getattr(raw_step, "step_number", 0) or 0
            # 模型本轮的「思考 + 代码」原文
            model_output = getattr(raw_step, "model_output", None)
            if model_output:
                thought, code = self._split_thought_and_code(str(model_output))
                if thought:
                    yield StreamEvent(kind="thought", text=thought, step=step_no)
                if code:
                    yield StreamEvent(kind="code", text=code, step=step_no)
            # 代码执行结果
            obs = getattr(raw_step, "observations", None)
            if obs:
                yield StreamEvent(kind="observation", text=str(obs), step=step_no)
            err = getattr(raw_step, "error", None)
            if err:
                yield StreamEvent(kind="error", text=str(err), step=step_no)
            return

        if cls_name == "PlanningStep":
            plan = getattr(raw_step, "plan", "") or ""
            if plan:
                yield StreamEvent(kind="plan", text=str(plan).strip())
            return

        if cls_name == "FinalAnswerStep":
            output = getattr(raw_step, "output", "")
            yield StreamEvent(kind="final", text=str(output))
            return

        # ChatMessageStreamDelta / ToolCall / ToolOutput / ActionOutput 暂不透出
        return

    @staticmethod
    def _split_thought_and_code(text: str) -> tuple[str, str]:
        """把 LLM 输出按代码块切成 thought 和 code 两段（取第一段代码）。"""
        # 兼容 ```py、```python、<code>...</code> 几种 fence
        match = re.search(r"```(?:python|py)?\s*\n([\s\S]+?)```", text)
        if not match:
            match = re.search(r"<code>\s*([\s\S]+?)\s*</code>", text)
        if not match:
            return text.strip(), ""
        code = match.group(1).strip()
        thought = (text[:match.start()] + text[match.end():]).strip()
        return thought, code

    def prepare(self, question: str) -> PreparedTurn:
        normalized_question = question.strip()
        intent = self._classify_intent(normalized_question)
        success_criteria = self._build_success_criteria(intent, normalized_question)
        tracked_goal = self._maybe_track_goal(normalized_question, success_criteria)
        memory_context = self.memory.format_context_for_question(normalized_question)

        prompt_parts = []
        if memory_context:
            prompt_parts.append(memory_context)

        plan_lines = [
            "=== 当前认知框架 ===",
            f"意图类型：{intent}",
            "请先在内部完成：理解目标 → 结合记忆 → 选择工具 → 自检答案。",
            "本轮完成标准：",
        ]
        for criterion in success_criteria:
            plan_lines.append(f"- {criterion}")

        prompt_parts.append("\n".join(plan_lines))
        prompt_parts.append(f"当前问题：{normalized_question}")

        return PreparedTurn(
            prompt="\n\n".join(prompt_parts),
            intent=intent,
            success_criteria=success_criteria,
            tracked_goal=tracked_goal,
        )

    def _classify_intent(self, question: str) -> str:
        lowered = question.lower()
        keyword_groups = {
            "automation": ("定时", "任务", "schedule", "cron", "提醒", "自动", "workflow"),
            "memory": ("记住", "remember", "偏好", "以后", "下次", "忘记"),
            "diagnostics": ("日志", "监控", "健康", "异常", "报错", "诊断", "检查", "error"),
            "building": ("实现", "优化", "重构", "添加", "修复", "改造", "搭建", "开发"),
            "analysis": ("为什么", "分析", "对比", "区别", "是否", "原理", "策略"),
        }
        for intent, keywords in keyword_groups.items():
            if any(keyword in lowered for keyword in keywords):
                return intent
        return "qa"

    def _build_success_criteria(self, intent: str, question: str) -> list[str]:
        criteria = ["回答必须直接对应用户问题，不偏题。"]
        if intent in {"building", "automation"}:
            criteria.extend(
                [
                    "优先复用现有工具和已有能力，不重复造轮子。",
                    "涉及执行或修改时，要覆盖关键联动面。",
                    "给出的结果要能直接落地，而不是停留在建议层。",
                ]
            )
        elif intent == "diagnostics":
            criteria.extend(
                [
                    "明确指出问题原因或最可能原因。",
                    "优先给出可执行的修复或排查路径。",
                ]
            )
        elif intent == "memory":
            criteria.extend(
                [
                    "区分短期上下文与长期偏好/事实。",
                    "避免与既有记忆冲突，如冲突需更新旧记忆。",
                ]
            )
        else:
            criteria.extend(
                [
                    "必要时结合记忆和实时工具信息。",
                    "输出尽量准确、简洁、可验证。",
                ]
            )

        if "步骤" in question or "plan" in question.lower():
            criteria.append("答案需要有清晰步骤结构。")
        return criteria

    def _maybe_track_goal(self, question: str, success_criteria: list[str]) -> str | None:
        if len(question) < 6:
            return None
        if not re.search(r"(优化|实现|修复|改造|添加|重构|搭建|长期|持续|计划|目标)", question):
            return None
        goal = f"处理目标：{self._trim(question, 120)}"
        self.memory.set_goal(goal, success_criteria="；".join(success_criteria), priority=1, status="active")
        return goal

    def _derive_lesson(self, intent: str, answer: str) -> str:
        if intent == "diagnostics":
            return "诊断类问题应先定位根因，再给最短修复路径。"
        if intent == "building":
            return "复杂改造应先组织目标和约束，再推进实现与联调。"
        if intent == "automation":
            return "自动化请求需要同时关注触发条件、执行动作和结果反馈。"
        if intent == "memory":
            return "涉及记忆时要优先保持事实一致性和长期可复用性。"
        if "无法" in answer or "失败" in answer:
            return "当答案存在阻塞时，应显式说明阻塞点，避免假装完成。"
        return "通用问答优先保持聚焦，并尽量结合已有记忆减少重复询问。"

    def _estimate_importance(self, question: str) -> float:
        base = 0.55
        if re.search(r"(优化|实现|修复|改造|长期|任务|记住|偏好)", question):
            base += 0.2
        if len(question) > 40:
            base += 0.1
        return min(base, 0.95)

    def _build_episode_summary(self, question: str, answer: str) -> str:
        return f"{self._trim(question, 72)} -> {self._trim(answer, 72)}"

    def _trim(self, text: str, limit: int) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= limit:
            return compact
        return compact[: limit - 3] + "..."
