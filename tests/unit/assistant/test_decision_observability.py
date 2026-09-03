from dataclasses import asdict
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

from langgraph.runtime import Runtime
from structlog.testing import capture_logs

from app.modules.assistant.domain.context import AssembledContext
from app.modules.assistant.domain.entities import (
    AssistantDecisionEvent,
    DecisionOutcome,
    DecisionStage,
    ToolCallRecord,
    ToolDescriptor,
    ToolOutcomeStatus,
)
from app.modules.assistant.infrastructure.agents.langgraph.context import (
    GraphContext,
    ToolCallBudget,
)
from app.modules.assistant.infrastructure.agents.langgraph.nodes.plan_action import plan_action
from app.modules.assistant.infrastructure.agents.langgraph.nodes.tool_call import invoke_tool
from app.modules.assistant.infrastructure.agents.langgraph.state import (
    CURRENT_WORKFLOW_VERSION,
    AgentStateView,
    GraphState,
    PlannedAction,
)
from app.modules.assistant.infrastructure.telemetry.orchestration_observability import (
    StructlogAssistantTelemetry,
)
from app.modules.user.domain.authorization import AuthorizationContext, RoleName

CONVERSATION_ID = UUID("11111111-1111-1111-1111-111111111111")


class RecordingBrain:
    async def classify_intent(self, state: AgentStateView) -> str:
        return "assistant_query"

    async def plan_action(self, state: AgentStateView) -> PlannedAction:
        return {
            "action": "tool_call",
            "tool_name": "web_search",
            "payload": {"query": "maintenance guidance"},
            "intent": "search_maintenance_guidance",
            "confidence": 0.91,
            "rationale": "Current public guidance requires web search.",
        }

    async def respond(self, state: AgentStateView) -> str:
        return "response"


class ResultInvoker:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result

    async def __call__(
        self,
        tool_name: str,
        payload: dict[str, object],
    ) -> ToolCallRecord:
        return ToolCallRecord(
            tool_name=tool_name,
            payload=payload,
            status=ToolOutcomeStatus.SUCCESS,
            evidence=(),
            result=self.result,
        )


def _state(
    descriptor: ToolDescriptor,
    *,
    payload: dict[str, object] | None = None,
) -> GraphState:
    return {
        "workflow_version": CURRENT_WORKFLOW_VERSION,
        "messages": [],
        "working_set": {"active_intent": None, "referenced_entities": []},
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
        "answer": "",
        "finish_reason": None,
    }


def _runtime(
    events: list[AssistantDecisionEvent],
    *,
    query: str = "Show me open work orders at PLANT-HCM",
    descriptor: ToolDescriptor | None = None,
    result: dict[str, object] | None = None,
) -> Runtime[GraphContext]:
    invoker = ResultInvoker(result or {"tool_name": "unused"})
    effective_descriptor = descriptor or ToolDescriptor(
        name="get_work_orders",
        description="test",
        site_code_field="site_code",
    )
    return cast(
        Runtime[GraphContext],
        SimpleNamespace(
            context=GraphContext(
                brain=RecordingBrain(),
                authorization_context=AuthorizationContext(
                    user_id=uuid4(),
                    roles=frozenset({RoleName.READ_ONLY_ANALYST}),
                    global_scope=True,
                ),
                available_tools=(effective_descriptor,),
                tool_invoker=invoker,
                call_budget=ToolCallBudget(remaining_calls=1, max_calls_per_tool=1),
                retrieved_context=AssembledContext(),
                user_query=query,
                conversation_id=CONVERSATION_ID,
                decision_observer=events.append,
            )
        ),
    )


async def test_deterministic_planning_emits_selected_decision_metadata() -> None:
    events: list[AssistantDecisionEvent] = []

    await plan_action(
        _state(
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
            ToolDescriptor(name="web_search", description="test"),
        ),
        _runtime(
            events,
            query="Find current public maintenance guidance",
            descriptor=ToolDescriptor(name="web_search", description="test"),
        ),
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
        authorization_context=AuthorizationContext(
            user_id=uuid4(),
            roles=frozenset({RoleName.READ_ONLY_ANALYST}),
            global_scope=True,
        ),
        available_tools=(),
        tool_invoker=ResultInvoker({"tool_name": "unused"}),
        call_budget=ToolCallBudget(remaining_calls=0, max_calls_per_tool=0),
        retrieved_context=AssembledContext(),
        user_query="test",
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
