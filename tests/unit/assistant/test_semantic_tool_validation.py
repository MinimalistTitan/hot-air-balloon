from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from langgraph.runtime import Runtime

from app.modules.assistant.domain.context import AssembledContext
from app.modules.assistant.domain.entities import (
    ToolCallRecord,
    ToolDescriptor,
    ToolOutcomeStatus,
)
from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from app.modules.assistant.infrastructure.agents.langgraph.context import (
    GraphContext,
    ToolCallBudget,
)
from app.modules.assistant.infrastructure.agents.langgraph.nodes.tool_call import invoke_tool
from app.modules.assistant.infrastructure.agents.langgraph.semantic_validation import (
    SemanticRejectionReason,
    validate_tool_call_semantics,
)
from app.modules.assistant.infrastructure.agents.langgraph.state import (
    CURRENT_WORKFLOW_VERSION,
    GraphState,
)
from app.modules.user.domain.authorization import AuthorizationContext, RoleName


def _descriptor(
    name: str,
    *,
    site_code_field: str | None = None,
    is_mutating: bool = False,
) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description="test tool",
        site_code_field=site_code_field,
        is_mutating=is_mutating,
    )


def test_semantic_validation_accepts_exact_deterministic_call() -> None:
    result = validate_tool_call_semantics(
        query="Show me open work orders at PLANT-HCM",
        descriptor=_descriptor("get_work_orders", site_code_field="site_code"),
        payload={"site_code": "plant-hcm", "status": "open"},
    )

    assert result.allowed
    assert result.reason is None


@pytest.mark.parametrize(
    ("descriptor", "payload", "reason"),
    [
        (
            _descriptor("get_production_schedule", site_code_field="site_code"),
            {"site_code": "PLANT-HCM"},
            SemanticRejectionReason.TOOL_MISMATCH,
        ),
        (
            _descriptor("get_work_orders", site_code_field="site_code"),
            {"status": "open"},
            SemanticRejectionReason.ENTITY_MISSING,
        ),
        (
            _descriptor("get_work_orders", site_code_field="site_code"),
            {"site_code": "PLANT-HN", "status": "open"},
            SemanticRejectionReason.ENTITY_MISMATCH,
        ),
        (
            _descriptor("get_work_orders", site_code_field="site_code"),
            {"site_code": "PLANT-HCM", "status": "completed"},
            SemanticRejectionReason.ENTITY_MISMATCH,
        ),
    ],
)
def test_semantic_validation_rejects_deterministic_mismatch(
    descriptor: ToolDescriptor,
    payload: dict[str, object],
    reason: SemanticRejectionReason,
) -> None:
    result = validate_tool_call_semantics(
        query="Show me open work orders at PLANT-HCM",
        descriptor=descriptor,
        payload=payload,
    )

    assert not result.allowed
    assert result.reason is reason


def test_semantic_validation_rejects_filter_not_present_in_request() -> None:
    result = validate_tool_call_semantics(
        query="Show me work orders at PLANT-HCM",
        descriptor=_descriptor("get_work_orders", site_code_field="site_code"),
        payload={"site_code": "PLANT-HCM", "status": "completed"},
    )

    assert not result.allowed
    assert result.reason is SemanticRejectionReason.UNEXPECTED_ENTITY


def test_semantic_validation_rejects_any_tool_for_direct_response() -> None:
    result = validate_tool_call_semantics(
        query="Explain a maintenance work order. Do not use tools",
        descriptor=_descriptor("write_work_order_status", is_mutating=True),
        payload={"work_order_code": "WO-HCM-0101", "target_status": "completed"},
    )

    assert not result.allowed
    assert result.reason is SemanticRejectionReason.TOOL_NOT_REQUESTED


def test_semantic_validation_checks_site_for_llm_fallback_call() -> None:
    result = validate_tool_call_semantics(
        query="Show work order WO-HCM-0101 at PLANT-HCM",
        descriptor=_descriptor("get_work_orders", site_code_field="site_code"),
        payload={"site_code": "PLANT-HN"},
    )

    assert not result.allowed
    assert result.reason is SemanticRejectionReason.ENTITY_MISMATCH


def test_semantic_validation_accepts_explicit_work_order_mutation() -> None:
    result = validate_tool_call_semantics(
        query="Change work order WO-HCM-0101 to completed at PLANT-HCM",
        descriptor=_descriptor("write_work_order_status", is_mutating=True),
        payload={
            "work_order_code": "wo-hcm-0101",
            "target_status": "complete",
            "site_code": "plant-hcm",
        },
    )

    assert result.allowed


def test_work_order_identifier_after_for_is_not_misread_as_site() -> None:
    result = validate_tool_call_semantics(
        query="Set status to in progress for WO-HCM-0101",
        descriptor=_descriptor("write_work_order_status", is_mutating=True),
        payload={
            "work_order_code": "WO-HCM-0101",
            "target_status": "in_progress",
        },
    )

    assert result.allowed


@pytest.mark.parametrize(
    "payload",
    [
        {
            "work_order_code": "WO-HCM-9999",
            "target_status": "completed",
            "site_code": "PLANT-HCM",
        },
        {
            "work_order_code": "WO-HCM-0101",
            "target_status": "cancelled",
            "site_code": "PLANT-HCM",
        },
        {
            "work_order_code": "WO-HCM-0101",
            "target_status": "completed",
            "site_code": "PLANT-HN",
        },
    ],
)
def test_semantic_validation_rejects_mutation_entity_mismatch(
    payload: dict[str, object],
) -> None:
    result = validate_tool_call_semantics(
        query="Change work order WO-HCM-0101 to completed at PLANT-HCM",
        descriptor=_descriptor("write_work_order_status", is_mutating=True),
        payload=payload,
    )

    assert not result.allowed
    assert result.reason is SemanticRejectionReason.ENTITY_MISMATCH


def test_semantic_validation_rejects_unvalidated_mutating_tool() -> None:
    result = validate_tool_call_semantics(
        query="Delete asset A-100",
        descriptor=_descriptor("delete_asset", is_mutating=True),
        payload={"asset_code": "A-100"},
    )

    assert not result.allowed
    assert result.reason is SemanticRejectionReason.MUTATION_NOT_SUPPORTED


class ToolInvokerSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def __call__(
        self,
        tool_name: str,
        payload: dict[str, object],
    ) -> ToolCallRecord:
        self.calls.append((tool_name, payload))
        return ToolCallRecord(
            tool_name=tool_name,
            payload=payload,
            status=ToolOutcomeStatus.SUCCESS,
            evidence=(),
            result={"work_orders": []},
        )


def _state(
    *,
    descriptor: ToolDescriptor,
    payload: dict[str, object],
) -> GraphState:
    return {
        "workflow_version": CURRENT_WORKFLOW_VERSION,
        "intent": "assistant_query",
        "planned_action": {
            "action": "tool_call",
            "tool_name": descriptor.name,
            "payload": payload,
        },
        "pending_call": None,
        "tool_calls": [],
        "next_step": "continue",
        "answer": "",
        "finish_reason": None,
    }


def _runtime(
    invoker: ToolInvokerSpy,
    *,
    query: str,
    descriptor: ToolDescriptor,
) -> Runtime[GraphContext]:
    return cast(
        Runtime[GraphContext],
        SimpleNamespace(
            context=GraphContext(
                brain=cast(Any, object()),
                authorization_context=AuthorizationContext(
                    user_id=uuid4(),
                    roles=frozenset({RoleName.READ_ONLY_ANALYST}),
                    global_scope=True,
                ),
                available_tools=(descriptor,),
                tool_invoker=invoker,
                call_budget=ToolCallBudget(remaining_calls=1, max_calls_per_tool=1),
                retrieved_context=AssembledContext(),
                user_query=query,
            ),
        ),
    )


async def test_tool_call_node_blocks_semantic_mismatch_before_invocation() -> None:
    invoker = ToolInvokerSpy()
    query = "Show me open work orders at PLANT-HCM"
    descriptor = _descriptor("get_work_orders", site_code_field="site_code")

    update = await invoke_tool(
        _state(
            descriptor=descriptor,
            payload={"site_code": "PLANT-HN", "status": "open"},
        ),
        _runtime(invoker, query=query, descriptor=descriptor),
    )

    assert update == {
        "answer": "Tool call blocked because it did not match the user's request.",
        "finish_reason": OrchestrationFinishReason.POLICY_BLOCKED,
    }
    assert invoker.calls == []


async def test_tool_call_node_blocks_unrequested_write_before_invocation() -> None:
    invoker = ToolInvokerSpy()
    query = "Explain what a maintenance work order is. Do not use tools"
    descriptor = _descriptor("write_work_order_status", is_mutating=True)

    update = await invoke_tool(
        _state(
            descriptor=descriptor,
            payload={
                "work_order_code": "WO-HCM-0101",
                "target_status": "completed",
            },
        ),
        _runtime(invoker, query=query, descriptor=descriptor),
    )

    assert update["finish_reason"] is OrchestrationFinishReason.POLICY_BLOCKED
    assert invoker.calls == []


async def test_tool_call_node_invokes_semantically_valid_call() -> None:
    invoker = ToolInvokerSpy()
    payload: dict[str, object] = {"site_code": "PLANT-HCM", "status": "open"}
    query = "Show me open work orders at PLANT-HCM"
    descriptor = _descriptor("get_work_orders", site_code_field="site_code")

    update = await invoke_tool(
        _state(
            descriptor=descriptor,
            payload=payload,
        ),
        _runtime(invoker, query=query, descriptor=descriptor),
    )

    assert invoker.calls == [("get_work_orders", payload)]
    pending_call = update["pending_call"]
    assert isinstance(pending_call, ToolCallRecord)
    assert pending_call.tool_name == "get_work_orders"
    assert pending_call.payload == payload
    assert pending_call.result == {"work_orders": []}
