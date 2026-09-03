from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from langgraph.runtime import Runtime

from app.modules.assistant.domain.context import AssembledContext
from app.modules.assistant.domain.entities import ToolCallRecord, ToolDescriptor
from app.modules.assistant.infrastructure.agents.langgraph.context import (
    GraphContext,
    ToolCallBudget,
)
from app.modules.assistant.infrastructure.agents.langgraph.deterministic_intent import (
    DeterministicIntent,
    resolve_intent,
)
from app.modules.assistant.infrastructure.agents.langgraph.nodes.decide_next_step import (
    decide_next_step,
)
from app.modules.assistant.infrastructure.agents.langgraph.nodes.plan_action import plan_action
from app.modules.assistant.infrastructure.agents.langgraph.state import (
    CURRENT_WORKFLOW_VERSION,
    AgentStateView,
    GraphState,
    PlannedAction,
)
from app.modules.user.domain.authorization import AuthorizationContext, RoleName


@pytest.mark.parametrize(
    ("query", "intent", "tool_name", "payload"),
    [
        (
            "Show me open work orders at PLANT-HCM",
            DeterministicIntent.LIST_WORK_ORDERS,
            "get_work_orders",
            {"site_code": "PLANT-HCM", "status": "open"},
        ),
        (
            "Show me three open work orders at PLANT-HCM",
            DeterministicIntent.LIST_WORK_ORDERS,
            "get_work_orders",
            {"site_code": "PLANT-HCM", "status": "open", "limit": 3},
        ),
        (
            "List the top 5 in-progress work orders for plant-hcm",
            DeterministicIntent.LIST_WORK_ORDERS,
            "get_work_orders",
            {"site_code": "PLANT-HCM", "status": "in_progress", "limit": 5},
        ),
        (
            "Get the first 8 maintenance tickets at HCM-ASIA-12",
            DeterministicIntent.LIST_MAINTENANCE_TICKETS,
            "get_maintenance_tickets",
            {"site_code": "HCM-ASIA-12", "limit": 8},
        ),
        (
            "Show spare parts stock in BK-ASIA-01, top 4",
            DeterministicIntent.CHECK_SPARE_PARTS,
            "get_spare_parts_availability",
            {"site_code": "BK-ASIA-01", "limit": 4},
        ),
        (
            "Show asset status at PLANT-HN",
            DeterministicIntent.GET_ASSET_STATUS,
            "get_asset_status",
            {"site_code": "PLANT-HN"},
        ),
        (
            "Which work orders are due soonest at PLANT-HCM?",
            DeterministicIntent.GET_PRODUCTION_SCHEDULE,
            "get_production_schedule",
            {"site_code": "PLANT-HCM"},
        ),
    ],
)
def test_resolve_intent_extracts_supported_entities(
    query: str,
    intent: DeterministicIntent,
    tool_name: str,
    payload: dict[str, object],
) -> None:
    resolution = resolve_intent(query)

    assert resolution is not None
    assert resolution.intent is intent
    assert resolution.tool_name == tool_name
    assert resolution.payload == payload


@pytest.mark.parametrize(
    "query",
    [
        "Explain what a maintenance work order is in one sentence. Do not use tools",
        "Define a maintenance work order",
        "What is a maintenance work order?",
    ],
)
def test_resolve_intent_forces_direct_response_for_informational_queries(query: str) -> None:
    resolution = resolve_intent(query)

    assert resolution is not None
    assert resolution.intent is DeterministicIntent.DIRECT_RESPONSE
    assert resolution.tool_name is None
    assert resolution.payload == {}


@pytest.mark.parametrize(
    "query",
    [
        "Help me with maintenance",
        "Show work order WO-HCM-0101",
    ],
)
def test_resolve_intent_leaves_unsupported_or_ambiguous_queries_to_the_planner(
    query: str,
) -> None:
    assert resolve_intent(query) is None


class RecordingBrain:
    def __init__(self) -> None:
        self.plan_calls = 0

    async def classify_intent(self, state: AgentStateView) -> str:
        return "assistant_query"

    async def plan_action(self, state: AgentStateView) -> PlannedAction:
        self.plan_calls += 1
        return {
            "action": "tool_call",
            "tool_name": "wrong_tool",
            "payload": {},
        }

    async def respond(self, state: AgentStateView) -> str:
        return "response"


async def _unused_tool_invoker(
    tool_name: str,
    payload: dict[str, object],
) -> ToolCallRecord:
    raise AssertionError(f"unexpected tool invocation: {tool_name} {payload}")


def _state() -> GraphState:
    return {
        "workflow_version": CURRENT_WORKFLOW_VERSION,
        "messages": [],
        "working_set": {"active_intent": None, "referenced_entities": []},
        "intent": "assistant_query",
        "planned_action": {"action": "respond", "tool_name": "", "payload": {}},
        "pending_call": None,
        "tool_calls": [],
        "answer": "",
        "finish_reason": None,
    }


def _runtime(
    brain: RecordingBrain,
    query: str,
    tool_names: list[str],
) -> Runtime[GraphContext]:
    return cast(
        Runtime[GraphContext],
        SimpleNamespace(
            context=GraphContext(
                brain=brain,
                authorization_context=AuthorizationContext(
                    user_id=uuid4(),
                    roles=frozenset({RoleName.READ_ONLY_ANALYST}),
                    global_scope=True,
                ),
                available_tools=tuple(
                    ToolDescriptor(name=tool_name, description="test") for tool_name in tool_names
                ),
                tool_invoker=_unused_tool_invoker,
                call_budget=ToolCallBudget(remaining_calls=1, max_calls_per_tool=1),
                retrieved_context=AssembledContext(),
                user_query=query,
            ),
        ),
    )


async def test_plan_action_routes_recognized_intent_without_calling_llm() -> None:
    brain = RecordingBrain()

    command = await plan_action(
        _state(),
        _runtime(
            brain,
            "Show me open work orders at PLANT-HCM",
            ["get_work_orders", "wrong_tool"],
        ),
    )

    assert command.goto == "tool_call"
    assert command.update is not None
    assert command.update["planned_action"] == {
        "action": "tool_call",
        "tool_name": "get_work_orders",
        "payload": {"site_code": "PLANT-HCM", "status": "open"},
    }
    assert brain.plan_calls == 0


async def test_plan_action_does_not_substitute_when_required_tool_is_unavailable() -> None:
    brain = RecordingBrain()

    command = await plan_action(
        _state(),
        _runtime(brain, "Show me open work orders at PLANT-HCM", ["wrong_tool"]),
    )

    assert command.goto == "respond"
    assert command.update is not None
    assert command.update["planned_action"] == {
        "action": "respond",
        "tool_name": "",
        "payload": {},
    }
    assert brain.plan_calls == 0


async def test_plan_action_honors_explicit_no_tool_instruction() -> None:
    brain = RecordingBrain()

    command = await plan_action(
        _state(),
        _runtime(brain, "Explain a work order. Don't use any tools", ["wrong_tool"]),
    )

    assert command.goto == "respond"
    assert command.update is not None
    assert command.update["planned_action"]["action"] == "respond"
    assert brain.plan_calls == 0


async def test_plan_action_uses_llm_fallback_for_unrecognized_query() -> None:
    brain = RecordingBrain()

    command = await plan_action(
        _state(),
        _runtime(brain, "Help me with maintenance", ["wrong_tool"]),
    )

    assert command.goto == "tool_call"
    assert command.update is not None
    assert command.update["planned_action"]["tool_name"] == "wrong_tool"
    assert brain.plan_calls == 1


async def test_decide_next_step_commands_another_plan_when_budget_remains() -> None:
    command = await decide_next_step(
        _state(),
        _runtime(RecordingBrain(), "Help me with maintenance", ["wrong_tool"]),
    )

    assert command.goto == "plan_action"
    assert command.update is None


async def test_decide_next_step_commands_response_when_budget_is_exhausted() -> None:
    runtime = _runtime(RecordingBrain(), "Help me with maintenance", ["wrong_tool"])
    runtime.context.call_budget.remaining_calls = 0

    command = await decide_next_step(_state(), runtime)

    assert command.goto == "respond"
    assert command.update is None
