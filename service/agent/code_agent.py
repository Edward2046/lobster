"""service/agent/code_agent.py — 带兜底清洗的 CodeAgent。

在标准 smolagents CodeAgent 之上，给底层 python_executor 包一层，
在执行前修复模型生成的坏代码（目前主要是 final_answer 未闭合的多行字符串）。
"""

from __future__ import annotations

from smolagents import CodeAgent

from service.agent.brain import sanitize_agent_code


class _SanitizingExecutor:
    """包一层 smolagents 的 python_executor，在执行前修复模型的坏代码。

    最典型的场景：模型把多行文本塞进 final_answer 的单层引号里，
    导致解释器抛 “unterminated string literal”。这里先做一次兜底清洗，
    其余属性（send_variables/send_tools/state/cleanup 等）透传给内层执行器。
    """

    def __init__(self, inner):
        self._inner = inner

    def __call__(self, code_action: str):
        return self._inner(sanitize_agent_code(code_action))

    def __getattr__(self, name):
        # _inner 是普通实例属性，正常查找即可命中，不会触发递归。
        return getattr(self._inner, name)


class LobsterCodeAgent(CodeAgent):
    """在标准 CodeAgent 基础上，给 python_executor 加一层坏代码兜底清洗。"""

    def create_python_executor(self):
        return _SanitizingExecutor(super().create_python_executor())
