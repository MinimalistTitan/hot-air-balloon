from typing import Protocol

from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState, PlannedAction


class AgentBrain(Protocol):
    """LLM-backed reasoning used by the LangGraph orchestration nodes."""

    async def classify_intent(self, state: GraphState) -> str: ...
    async def plan_action(self, state: GraphState) -> PlannedAction: ...
    async def respond(self, state: GraphState) -> str: ...