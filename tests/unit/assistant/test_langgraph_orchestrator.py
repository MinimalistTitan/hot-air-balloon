from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from langgraph.runtime import Runtime

from app.modules.assistant.domain.context import AssembledContext, ContextBlock, ContextKind
from app.modules.assistant.domain.entities import ToolDescriptor
from app.modules.assistant.domain.tool_call import ToolCallPolicy
from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.nodes.respond import (
    respond as respond_node,
)
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


class RecordingBrain:
    def __init__(self) -> None:
        self.answers_seen_in_respond: list[str] = []
        self.contexts_seen_in_respond: list[str] = []

    async def classify_intent(self, state: GraphState) -> str:
        return "assistant_query"

    async def plan_action(self, state: GraphState) -> PlannedAction:
        return {"action": "respond", "tool_name": "", "payload": {}}

    async def respond(self, state: GraphState) -> str:
        self.answers_seen_in_respond.append(state["answer"])
        self.contexts_seen_in_respond.append(state["context_prompt"])
        return "Fresh answer for the current query."


async def _fail_invoker(tool_name: str, payload: dict[str, object]) -> dict[str, object]:
    raise AssertionError(f"tool_invoker must not be called, got {tool_name}")


def _context_with_sentinel(text: str) -> AssembledContext:
    return AssembledContext(
        blocks=[
            ContextBlock(
                kind=ContextKind.SYSTEM_DIRECTIVE,
                content=text,
                source="test",
            )
        ],
        total_tokens=0,
        dropped_block_count=0,
    )


def _respond_state(
    *,
    answer: str,
    finish_reason: OrchestrationFinishReason | None,
) -> GraphState:
    return {
        "user_query": "Explain what a maintenance work order is in one sentence",
        "context_prompt": "SENTINEL-CONTEXT",
        "available_tools": [],
        "conversation_history": [],
        "intent": "assistant_query",
        "planned_action": {"action": "respond", "tool_name": "", "payload": {}},
        "pending_call": None,
        "tool_calls": [],
        "total_tool_calls": 0,
        "per_tool_calls": {},
        "remaining_tool_calls": 0,
        "max_calls_per_tool": 1,
        "next_step": "respond",
        "answer": answer,
        "finish_reason": finish_reason,
    }


def _runtime(brain: RecordingBrain) -> Runtime[GraphContext]:
    return cast(
        Runtime[GraphContext],
        SimpleNamespace(
            context=GraphContext(brain=brain, tool_invoker=_fail_invoker),
        ),
    )


async def test_orchestrator_never_seeds_answer_with_rendered_context() -> None:
    brain = RecordingBrain()

    result = await LangGraphAgentOrchestrator(
        brain=brain,
        model_name="test-model",
    ).run(
        conversation_id=uuid4(),
        user_query="Explain what a maintenance work order is in one sentence",
        available_tools=[],
        tool_invoker=_fail_invoker,
        context=_context_with_sentinel("SENTINEL-CONTEXT"),
        tool_policy=ToolCallPolicy(
            allowed_tool_names=frozenset(),
            max_total_calls=0,
            max_calls_per_tool=0,
        ),
        max_tool_calls=0,
        allow_tool_calls=False,
    )

    assert result.answer == "Fresh answer for the current query."
    # Regression: the answer channel must start empty. Seeding it with the
    # rendered context let a short-circuited respond node replay the previous
    # conversation as the answer.
    assert brain.answers_seen_in_respond == [""]
    # The assembled context reaches the brain as prompt data instead.
    assert brain.contexts_seen_in_respond == ["[System Directive] SENTINEL-CONTEXT"]
    assert result.tool_calls == []


async def test_respond_regenerates_answer_when_terminal_reason_has_no_answer() -> None:
    update = await respond_node(
        _respond_state(answer="", finish_reason=OrchestrationFinishReason.POLICY_BLOCKED),
        _runtime(RecordingBrain()),
    )

    assert update["answer"] == "Fresh answer for the current query."
    # The terminal reason is preserved, not masked as completed.
    assert "finish_reason" not in update


async def test_respond_preserves_terminal_answer() -> None:
    update = await respond_node(
        _respond_state(
            answer="Tool call blocked by policy.",
            finish_reason=OrchestrationFinishReason.POLICY_BLOCKED,
        ),
        _runtime(RecordingBrain()),
    )

    assert update == {}
