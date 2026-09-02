from typing import Protocol

from app.modules.assistant.infrastructure.agents.langgraph.state import (
    AgentStateView,
    PlannedAction,
)


class AgentBrain(Protocol):
    """LLM-backed reasoning used by the LangGraph orchestration nodes."""

    async def classify_intent(self, state: AgentStateView) -> str: ...
    async def plan_action(self, state: AgentStateView) -> PlannedAction: ...
    async def respond(self, state: AgentStateView) -> str: ...
