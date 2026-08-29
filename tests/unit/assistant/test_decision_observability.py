from dataclasses import asdict
from types import SimpleNamespace
from typing import cast
from uuid import UUID

from langgraph.runtime import Runtime
from structlog.testing import capture_logs

from app.modules.assistant.domain.entities import (
    AssistantDecisionEvent,
    DecisionOutcome,
    DecisionStage,
    ToolDescriptor,
)
from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.nodes.plan_action import plan_action
from app.modules.assistant.infrastructure.agents.langgraph.nodes.tool_call import invoke_tool
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState, PlannedAction
from app.modules.assistant.infrastructure.telemetry.orchestration_observability import (
    StructlogAssistantTelemetry,
)

CONVERSATION_ID = UUID("11111111-1111-1111-1111-111111111111")


class RecordingBrain:
    async def classify_intent(self, state: GraphState) -> str:
        return "assistant_query"

    async def plan_action(self, state: GraphState) -> PlannedAction:
        return {
            "action": "tool_call",
            "tool_name": "web_search",
            "payload": {"query": "maintenance guidance"},
            "intent": "search_maintenance_guidance",
            "confidence": 0.91,
            "rationale": "Current public guidance requires web search.",
        }

    async def respond(self, state: GraphState) -> str:
        return "response"


class ResultInvoker:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result

    async def __call__(
        self,
        tool_name: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        return self.result


def _state(
    query: str,
    descriptor: ToolDescriptor,
    *,
    payload: dict[str, object] | None = None,
) -> GraphState:
    return {
        "user_query": query,
        "context_prompt": "",
        "available_tools": [descriptor],
        "conversation_history": [],
        "intent": "assistant_query",
        "planned_action": {
            "action": "tool_call",
            "tool_name": descriptor.name,
            "payload": payload or {},
            "intent": "list_open_work_orders",
            "confidence": 0.96,
            "rationale": "The request matches the work-order tool.",
        },
        "pending_call": None,
        "tool_calls": [],
        "total_tool_calls": 0,
        "per_tool_calls": {},
        "remaining_tool_calls": 1,
        "max_calls_per_tool": 1,
        "next_step": "continue",
        "answer": "",
        "finish_reason": None,
    }


def _runtime(
    events: list[AssistantDecisionEvent],
    *,
    result: dict[str, object] | None = None,
) -> Runtime[GraphContext]:
    invoker = ResultInvoker(result or {"tool_name": "unused"})
    return cast(
        Runtime[GraphContext],
        SimpleNamespace(
            context=GraphContext(
                brain=RecordingBrain(),
                tool_invoker=invoker,
                conversation_id=CONVERSATION_ID,
                decision_observer=events.append,
            )
        ),
    )


async def test_deterministic_planning_emits_selected_decision_metadata() -> None:
    events: list[AssistantDecisionEvent] = []

    await plan_action(
        _state(
            "Show me open work orders at PLANT-HCM",
            ToolDescriptor(
                name="get_work_orders",
                description="test",
                site_code_field="site_code",
            ),
        ),
        _runtime(events),
    )

    assert events == [
        AssistantDecisionEvent(
            conversation_id=CONVERSATION_ID,
            stage=DecisionStage.PLANNING,
            outcome=DecisionOutcome.SELECTED,
            source="deterministic",
            intent="list_work_orders",
            confidence=1.0,
            action="tool_call",
            tool_name="get_work_orders",
            callable_tool_count=1,
        )
    ]


async def test_model_planning_emits_confidence_without_rationale_or_payload() -> None:
    events: list[AssistantDecisionEvent] = []

    await plan_action(
        _state(
            "Find current public maintenance guidance",
            ToolDescriptor(name="web_search", description="test"),
        ),
        _runtime(events),
    )

    event = events[0]
    assert event.source == "model"
    assert event.intent == "search_maintenance_guidance"
    assert event.confidence == 0.91
    assert event.tool_name == "web_search"
    assert "payload" not in asdict(event)
    assert "rationale" not in asdict(event)
    assert "query" not in asdict(event)


async def test_semantic_rejection_emits_stable_reason_code() -> None:
    events: list[AssistantDecisionEvent] = []

    await invoke_tool(
        _state(
            "Show me open work orders at PLANT-HCM",
            ToolDescriptor(
                name="get_work_orders",
                description="test",
                site_code_field="site_code",
            ),
            payload={"site_code": "PLANT-HN", "status": "open"},
        ),
        _runtime(events),
    )

    assert len(events) == 1
    assert events[0].stage is DecisionStage.PRE_EXECUTION
    assert events[0].outcome is DecisionOutcome.BLOCKED
    assert events[0].source == "semantic_validator"
    assert events[0].reason_code == "entity_mismatch"


async def test_result_rejection_emits_allowed_precheck_then_blocked_result() -> None:
    events: list[AssistantDecisionEvent] = []
    result: dict[str, object] = {
        "status": "success",
        "tool_name": "get_work_orders",
        "applied_payload": {"site_code": "PLANT-HCM", "status": "open", "limit": 10},
        "result": {
            "tool_name": "get_work_orders",
            "work_orders": [{"code": "WO-HN-0101", "site_code": "PLANT-HN", "status": "open"}],
        },
    }

    await invoke_tool(
        _state(
            "Show me open work orders at PLANT-HCM",
            ToolDescriptor(
                name="get_work_orders",
                description="test",
                site_code_field="site_code",
            ),
            payload={"site_code": "PLANT-HCM", "status": "open"},
        ),
        _runtime(events, result=result),
    )

    assert [(event.stage, event.outcome, event.reason_code) for event in events] == [
        (DecisionStage.PRE_EXECUTION, DecisionOutcome.ALLOWED, None),
        (
            DecisionStage.RESULT_VALIDATION,
            DecisionOutcome.BLOCKED,
            "result_entity_mismatch",
        ),
    ]


def test_observer_failure_does_not_change_orchestration_behavior() -> None:
    def fail_observer(event: AssistantDecisionEvent) -> None:
        raise RuntimeError("telemetry unavailable")

    context = GraphContext(
        brain=RecordingBrain(),
        tool_invoker=ResultInvoker({"tool_name": "unused"}),
        decision_observer=fail_observer,
    )

    context.record_decision(
        AssistantDecisionEvent(
            conversation_id=None,
            stage=DecisionStage.PLANNING,
            outcome=DecisionOutcome.SELECTED,
            source="test",
        )
    )


def test_structlog_decision_event_contains_only_bounded_metadata() -> None:
    event = AssistantDecisionEvent(
        conversation_id=CONVERSATION_ID,
        stage=DecisionStage.PRE_EXECUTION,
        outcome=DecisionOutcome.BLOCKED,
        source="semantic_validator",
        intent="list_work_orders",
        confidence=0.96,
        action="tool_call",
        tool_name="get_work_orders",
        reason_code="entity_mismatch",
        callable_tool_count=1,
    )

    with capture_logs() as logs:
        StructlogAssistantTelemetry().decision_recorded(event)

    assert logs == [
        {
            "event": "assistant_decision_recorded",
            "log_level": "info",
            "conversation_id": str(CONVERSATION_ID),
            "stage": "pre_execution",
            "outcome": "blocked",
            "source": "semantic_validator",
            "intent": "list_work_orders",
            "confidence": 0.96,
            "action": "tool_call",
            "tool_name": "get_work_orders",
            "reason_code": "entity_mismatch",
            "callable_tool_count": 1,
        }
    ]
