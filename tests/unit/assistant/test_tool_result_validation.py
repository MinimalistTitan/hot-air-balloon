from types import SimpleNamespace
from typing import cast

import pytest
from langgraph.runtime import Runtime

from app.modules.assistant.domain.entities import ToolCallRecord, ToolDescriptor
from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.nodes.tool_call import invoke_tool
from app.modules.assistant.infrastructure.agents.langgraph.result_validation import (
    ResultRejectionReason,
    validate_tool_result,
)
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState


def _work_order(
    *,
    code: str = "WO-HCM-0101",
    site_code: str = "PLANT-HCM",
    status: str = "open",
) -> dict[str, object]:
    return {"code": code, "site_code": site_code, "status": status}


def _gateway_result(
    *,
    tool_name: str = "get_work_orders",
    applied_payload: dict[str, object] | None = None,
    business_result: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "status": "success",
        "tool_name": tool_name,
        "applied_payload": applied_payload
        if applied_payload is not None
        else {"site_code": "PLANT-HCM", "status": "open", "limit": 10},
        "result": business_result
        if business_result is not None
        else {"tool_name": tool_name, "work_orders": [_work_order()]},
    }


def test_result_validation_accepts_matching_gateway_result() -> None:
    result = validate_tool_result(
        query="Show me open work orders at PLANT-HCM",
        tool_name="get_work_orders",
        payload={"site_code": "PLANT-HCM", "status": "open"},
        result=_gateway_result(),
    )

    assert result.allowed
    assert result.reason is None


@pytest.mark.parametrize(
    ("tool_result", "reason"),
    [
        (
            _gateway_result(tool_name="get_production_schedule"),
            ResultRejectionReason.TOOL_IDENTITY_MISMATCH,
        ),
        (
            _gateway_result(business_result={"tool_name": "get_asset_status", "work_orders": []}),
            ResultRejectionReason.TOOL_IDENTITY_MISMATCH,
        ),
        (
            _gateway_result(
                applied_payload={
                    "site_code": "PLANT-HN",
                    "status": "open",
                    "limit": 10,
                }
            ),
            ResultRejectionReason.APPLIED_PAYLOAD_MISMATCH,
        ),
    ],
)
def test_result_validation_rejects_envelope_mismatch(
    tool_result: dict[str, object],
    reason: ResultRejectionReason,
) -> None:
    result = validate_tool_result(
        query="Show me open work orders at PLANT-HCM",
        tool_name="get_work_orders",
        payload={"site_code": "PLANT-HCM", "status": "open"},
        result=tool_result,
    )

    assert not result.allowed
    assert result.reason is reason


@pytest.mark.parametrize(
    ("record", "reason"),
    [
        (_work_order(site_code="PLANT-HN"), ResultRejectionReason.RESULT_ENTITY_MISMATCH),
        (_work_order(status="completed"), ResultRejectionReason.RESULT_ENTITY_MISMATCH),
        (
            {"code": "WO-HCM-0101", "status": "open"},
            ResultRejectionReason.RESULT_ENTITY_MISSING,
        ),
    ],
)
def test_result_validation_rejects_conflicting_work_order_record(
    record: dict[str, object],
    reason: ResultRejectionReason,
) -> None:
    result = validate_tool_result(
        query="Show me open work orders at PLANT-HCM",
        tool_name="get_work_orders",
        payload={"site_code": "PLANT-HCM", "status": "open"},
        result=_gateway_result(
            business_result={"tool_name": "get_work_orders", "work_orders": [record]}
        ),
    )

    assert not result.allowed
    assert result.reason is reason


def test_result_validation_enforces_applied_limit() -> None:
    result = validate_tool_result(
        query="Show the first work order at PLANT-HCM",
        tool_name="get_work_orders",
        payload={"site_code": "PLANT-HCM", "limit": 1},
        result=_gateway_result(
            applied_payload={"site_code": "PLANT-HCM", "status": None, "limit": 1},
            business_result={
                "tool_name": "get_work_orders",
                "work_orders": [_work_order(), _work_order(code="WO-HCM-0102")],
            },
        ),
    )

    assert not result.allowed
    assert result.reason is ResultRejectionReason.COLLECTION_TOO_LARGE


def test_result_validation_does_not_apply_list_limit_to_asset_status() -> None:
    result = validate_tool_result(
        query="Show asset status at PLANT-HCM",
        tool_name="get_asset_status",
        payload={"site_code": "PLANT-HCM"},
        result={
            "tool_name": "get_asset_status",
            "assets": [
                {"code": f"ASSET-{index}", "site_code": "PLANT-HCM", "status": "available"}
                for index in range(11)
            ],
        },
    )

    assert result.allowed


def test_result_validation_rejects_unrelated_nonempty_specific_work_order_result() -> None:
    result = validate_tool_result(
        query="Show work order WO-HCM-9999 at PLANT-HCM",
        tool_name="get_work_orders",
        payload={"site_code": "PLANT-HCM"},
        result=_gateway_result(
            applied_payload={"site_code": "PLANT-HCM", "status": None, "limit": 10},
        ),
    )

    assert not result.allowed
    assert result.reason is ResultRejectionReason.RESULT_ENTITY_MISMATCH


def test_result_validation_accepts_empty_specific_work_order_result() -> None:
    result = validate_tool_result(
        query="Show work order WO-HCM-9999 at PLANT-HCM",
        tool_name="get_work_orders",
        payload={"site_code": "PLANT-HCM"},
        result=_gateway_result(
            applied_payload={"site_code": "PLANT-HCM", "status": None, "limit": 10},
            business_result={"tool_name": "get_work_orders", "work_orders": []},
        ),
    )

    assert result.allowed


def test_result_validation_rejects_invalid_maintenance_status() -> None:
    result = validate_tool_result(
        query="Show maintenance tickets at PLANT-HCM",
        tool_name="get_maintenance_tickets",
        payload={"site_code": "PLANT-HCM"},
        result={
            "tool_name": "get_maintenance_tickets",
            "tickets": [{"code": "WO-HCM-0101", "site_code": "PLANT-HCM", "status": "completed"}],
        },
    )

    assert not result.allowed
    assert result.reason is ResultRejectionReason.RESULT_ENTITY_MISMATCH


def test_result_validation_rejects_unsorted_production_schedule() -> None:
    result = validate_tool_result(
        query="Show production schedule at PLANT-HCM",
        tool_name="get_production_schedule",
        payload={"site_code": "PLANT-HCM"},
        result={
            "tool_name": "get_production_schedule",
            "schedule": [
                {"site_code": "PLANT-HCM", "due_at": "2026-08-27T08:00:00+00:00"},
                {"site_code": "PLANT-HCM", "due_at": "2026-08-26T08:00:00+00:00"},
            ],
        },
    )

    assert not result.allowed
    assert result.reason is ResultRejectionReason.RESULT_ORDER_MISMATCH


def test_result_validation_checks_successful_write_result() -> None:
    result = validate_tool_result(
        query="Change work order WO-HCM-0101 to completed",
        tool_name="write_work_order_status",
        payload={"work_order_code": "WO-HCM-0101", "target_status": "completed"},
        result={
            "tool_name": "write_work_order_status",
            "succeeded": True,
            "work_order_code": "WO-HCM-0101",
            "current_status": "open",
        },
    )

    assert not result.allowed
    assert result.reason is ResultRejectionReason.RESULT_ENTITY_MISMATCH


def test_result_validation_accepts_non_success_execution_outcome() -> None:
    result = validate_tool_result(
        query="Show me open work orders at PLANT-HCM",
        tool_name="get_work_orders",
        payload={"site_code": "PLANT-HCM", "status": "open"},
        result={
            "status": "rate_limited",
            "tool_name": "get_work_orders",
            "retry_after_seconds": 30,
        },
    )

    assert result.allowed


class ResultInvoker:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.calls = 0

    async def __call__(
        self,
        tool_name: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        self.calls += 1
        return self.result


def _state() -> GraphState:
    return {
        "user_query": "Show me open work orders at PLANT-HCM",
        "context_prompt": "",
        "available_tools": [
            ToolDescriptor(
                name="get_work_orders",
                description="test",
                site_code_field="site_code",
            )
        ],
        "conversation_history": [],
        "intent": "list_work_orders",
        "planned_action": {
            "action": "tool_call",
            "tool_name": "get_work_orders",
            "payload": {"site_code": "PLANT-HCM", "status": "open"},
        },
        "pending_call": None,
        "tool_calls": [],
        "total_tool_calls": 0,
        "per_tool_calls": {},
        "remaining_tool_calls": 1,
        "max_calls_per_tool": 1,
        "answer": "",
        "finish_reason": None,
    }


def _runtime(invoker: ResultInvoker) -> Runtime[GraphContext]:
    return cast(
        Runtime[GraphContext],
        SimpleNamespace(context=SimpleNamespace(tool_invoker=invoker)),
    )


async def test_tool_call_node_blocks_mismatched_result_before_observation() -> None:
    invoker = ResultInvoker(
        _gateway_result(
            business_result={
                "tool_name": "get_work_orders",
                "work_orders": [_work_order(site_code="PLANT-HN")],
            }
        )
    )

    command = await invoke_tool(_state(), _runtime(invoker))

    assert invoker.calls == 1
    assert command.goto == "respond"
    assert command.update == {
        "answer": "Tool result blocked because it did not match the user's request.",
        "finish_reason": OrchestrationFinishReason.POLICY_BLOCKED,
    }


async def test_tool_call_node_keeps_matching_result_for_observation() -> None:
    tool_result = _gateway_result()
    invoker = ResultInvoker(tool_result)

    command = await invoke_tool(_state(), _runtime(invoker))

    assert command.goto == "observe_result"
    assert command.update is not None
    pending_call = command.update["pending_call"]
    assert isinstance(pending_call, ToolCallRecord)
    assert pending_call.tool_name == "get_work_orders"
    assert pending_call.result == {
        key: value for key, value in tool_result.items() if key != "tool_name"
    }
