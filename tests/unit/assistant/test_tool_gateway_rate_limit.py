from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel, ConfigDict

from app.modules.assistant.tool_gateway.domain import (
    ToolApprovalDecision,
    ToolAuditRecord,
    ToolDefinition,
    ToolExecutionStatus,
    ToolRateLimit,
    ToolTraceEvent,
)
from app.modules.assistant.tool_gateway.gateway import ToolGateway
from app.modules.assistant.tool_gateway.permissions import DefaultPermissionChecker
from app.modules.assistant.tool_gateway.policy import PolicyApprovalService
from app.modules.assistant.tool_gateway.rate_limit import FixedWindowRateLimiter
from app.modules.assistant.tool_gateway.registry import ToolRegistry
from app.modules.user.domain.authorization import (
    AuthorizationContext,
    Permission,
    RoleName,
)

ACTOR_ONE_ID = UUID("11111111-1111-1111-1111-111111111111")
ACTOR_TWO_ID = UUID("22222222-2222-2222-2222-222222222222")


class ReadWorkOrdersInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_code: str


class ReadWorkOrdersOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = "read_work_orders"
    count: int


class RecordingAuditSink:
    def __init__(self) -> None:
        self.records: list[ToolAuditRecord] = []

    async def write(self, record: ToolAuditRecord) -> None:
        self.records.append(record)


class RecordingTraceSink:
    def __init__(self) -> None:
        self.events: list[ToolTraceEvent] = []

    async def append(self, event: ToolTraceEvent) -> None:
        self.events.append(event)


class FakeClock:
    def __init__(self, *, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class HandlerSpy:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return {"tool_name": "read_work_orders", "count": len(self.calls)}


def build_gateway(
    handler: HandlerSpy,
    clock: FakeClock,
    audit_sink: RecordingAuditSink,
    trace_sink: RecordingTraceSink,
) -> ToolGateway:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="read_work_orders",
            description="Read work orders",
            input_model=ReadWorkOrdersInput,
            output_model=ReadWorkOrdersOutput,
            handler=handler,
            required_permission=Permission.WORK_ORDERS_READ,
            site_code_field="site_code",
            rate_limit=ToolRateLimit(max_calls=2, window_seconds=60),
        )
    )

    return ToolGateway(
        registry=registry,
        permission_checker=DefaultPermissionChecker(),
        approval_service=PolicyApprovalService(),
        audit_sink=audit_sink,
        trace_sink=trace_sink,
        rate_limiter=FixedWindowRateLimiter(clock=clock),
    )


def authorization_context(user_id: UUID) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user_id,
        roles=frozenset({RoleName.MAINTENANCE_TECHNICIAN}),
        site_codes=frozenset({"HN-01"}),
    )


async def test_gateway_denies_call_beyond_rate_limit_without_reaching_handler() -> None:
    handler = HandlerSpy()
    clock = FakeClock()
    audit_sink = RecordingAuditSink()
    trace_sink = RecordingTraceSink()
    gateway = build_gateway(handler, clock, audit_sink, trace_sink)

    for _ in range(2):
        allowed_result = await gateway.invoke(
            tool_name="read_work_orders",
            payload={"site_code": "HN-01"},
            authorization_context=authorization_context(ACTOR_ONE_ID),
        )
        assert allowed_result["status"] == ToolExecutionStatus.SUCCESS.value

    clock.advance(10)
    denied_result = await gateway.invoke(
        tool_name="read_work_orders",
        payload={"site_code": "HN-01"},
        authorization_context=authorization_context(ACTOR_ONE_ID),
    )

    assert denied_result == {
        "status": ToolExecutionStatus.RATE_LIMITED.value,
        "tool_name": "read_work_orders",
        "retry_after_seconds": 50,
    }
    assert len(handler.calls) == 2
    assert audit_sink.records[-1].decision == ToolApprovalDecision.RATE_LIMITED
    assert trace_sink.events[-1].event == "rate_limited"


async def test_rate_limit_counter_is_isolated_per_actor() -> None:
    handler = HandlerSpy()
    clock = FakeClock()
    gateway = build_gateway(handler, clock, RecordingAuditSink(), RecordingTraceSink())

    for _ in range(2):
        await gateway.invoke(
            tool_name="read_work_orders",
            payload={"site_code": "HN-01"},
            authorization_context=authorization_context(ACTOR_ONE_ID),
        )

    other_actor_result = await gateway.invoke(
        tool_name="read_work_orders",
        payload={"site_code": "HN-01"},
        authorization_context=authorization_context(ACTOR_TWO_ID),
    )

    assert other_actor_result["status"] == ToolExecutionStatus.SUCCESS.value
    assert len(handler.calls) == 3


async def test_rate_limit_window_resets_after_expiry() -> None:
    handler = HandlerSpy()
    clock = FakeClock()
    gateway = build_gateway(handler, clock, RecordingAuditSink(), RecordingTraceSink())

    for _ in range(2):
        await gateway.invoke(
            tool_name="read_work_orders",
            payload={"site_code": "HN-01"},
            authorization_context=authorization_context(ACTOR_ONE_ID),
        )

    clock.advance(60)
    result = await gateway.invoke(
        tool_name="read_work_orders",
        payload={"site_code": "HN-01"},
        authorization_context=authorization_context(ACTOR_ONE_ID),
    )

    assert result["status"] == ToolExecutionStatus.SUCCESS.value
    assert len(handler.calls) == 3


async def test_gateway_denies_cross_site_call_before_handler_execution() -> None:
    handler = HandlerSpy()
    audit_sink = RecordingAuditSink()
    trace_sink = RecordingTraceSink()
    gateway = build_gateway(handler, FakeClock(), audit_sink, trace_sink)

    with pytest.raises(PermissionError, match="tool not allowed"):
        await gateway.invoke(
            tool_name="read_work_orders",
            payload={"site_code": "HN-02"},
            authorization_context=authorization_context(ACTOR_ONE_ID),
        )

    assert handler.calls == []
    assert audit_sink.records[-1].decision == ToolApprovalDecision.REJECTED
    assert trace_sink.events[-1].event == "permission_denied"
