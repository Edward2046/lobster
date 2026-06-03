"""Lobster Agent 编排层。

对外接口：
- LobsterBrain：认知编排
- get_prompt_templates：系统提示词
- agent / brain / run_once / interactive：CLI 运行时
"""

from service.agent.brain import LobsterBrain
from service.agent.prompt import get_prompt_templates

__all__ = ["LobsterBrain", "get_prompt_templates"]
