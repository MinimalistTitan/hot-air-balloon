from typing import Any, cast
from uuid import uuid4

from app.modules.assistant.domain.entities import ToolDescriptor
from app.modules.assistant.domain.tool_call import ToolCallPolicy
from app.modules.assistant.infrastructure.agents.langgraph.orchestrator import (
    LangGraphAgentOrchestrator,
)
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState, PlannedAction


class FakeBrain:
    async def classify_intent(self, state: GraphState) -> str:
        return "asset_status"

    async def plan_action(self, state: GraphState) -> PlannedAction:
        if not state["tool_calls"]:
            return {
                "action": "tool_call",
                "tool_name": "asset_status",
                "payload": {"asset_id": "A-1"},
            }
        return {"action": "respond", "tool_name": "", "payload": {}}

    async def respond(self, state: GraphState) -> str:
        return f"Asset is {state['tool_calls'][0].result['status']}."


async def test_orchestrator_runs_tool_loop_and_returns_trace() -> None:
    async def invoke_tool(
        tool_name: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        return {
            "tool_name": tool_name,
            "asset_id": payload["asset_id"],
            "status": "available",
        }

    result = await LangGraphAgentOrchestrator(
        brain=FakeBrain(),
        model_name="test-model",
    ).run(
        conversation_id=uuid4(),
        user_query="What is the status of A-1?",
        available_tools=[ToolDescriptor(name="asset_status", description="Read asset status")],
        tool_invoker=invoke_tool,
        context=cast(Any, type("Ctx", (), {"render": lambda self: ""})()),
        tool_policy=ToolCallPolicy(
            allowed_tool_names=frozenset({"asset_status"}),
            max_total_calls=1,
            max_calls_per_tool=1,
        ),
        max_tool_calls=1,
        allow_tool_calls=True,
    )

    assert result.answer == "Asset is available."
    assert result.finish_reason.value == "completed"
    assert result.tool_calls[0].tool_name == "asset_status"
    assert result.tool_calls[0].result == {"asset_id": "A-1", "status": "available"}
