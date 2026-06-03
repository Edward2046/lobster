"""
brain.py — Lobster 的轻量认知编排层

负责：
  1. 基于多层记忆构建上下文
  2. 为每轮请求注入意图、计划与成功标准
  3. 在执行后保存情景记忆、反思和目标状态
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

from service.memory.manager import MemoryManager, get_memory_manager


Runner = Callable[[str], object]


@dataclass
class PreparedTurn:
    prompt: str
    intent: str
    success_criteria: list[str]
    tracked_goal: str | None


class LobsterBrain:
    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        self.memory = memory_manager or get_memory_manager()

    def answer(self, question: str, runner: Runner, *, session_id: str | None = None) -> str:
        prepared = self.prepare(question)
        try:
            answer = str(runner(prepared.prompt))
        except Exception as exc:
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
