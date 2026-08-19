from dataclasses import dataclass

from app.modules.assistant.application.ports import ToolInvoker
from app.modules.assistant.infrastructure.agents.langgraph.contracts import AgentBrain


@dataclass(frozen=True, slots=True)
class GraphContext:
    brain: AgentBrain
    tool_invoker: ToolInvoker