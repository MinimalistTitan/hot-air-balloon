from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.modules.assistant.tool_gateway.domain import ToolDefinition
from app.modules.operations.application.ports import WorkOrderStatusSnapshot
from app.modules.operations.domain.manufacturing_maintenance.work_order_status import (
    WorkOrderStatus,
)
from app.modules.operations.infrastructure.tools.write_work_order_status_tool import (
    build_write_work_order_status_tool,
)
from app.modules.user.domain.authorization import Permission

WORK_ORDER_ID = UUID("11111111-1111-1111-1111-111111111111")
UPDATED_AT = datetime(2026, 8, 17, 9, 30, tzinfo=UTC)


class FakeWorkOrderStatusStore:
    def __init__(self, snapshot: WorkOrderStatusSnapshot | None) -> None:
        self._snapshot = snapshot
        self.applied: list[tuple[WorkOrderStatus, WorkOrderStatus]] = []
        self.conflict = False

    async def find_status_by_code(self, work_order_code: str) -> WorkOrderStatusSnapshot | None:
        if self._snapshot is None or self._snapshot.code != work_order_code:
            return None
        return self._snapshot

    async def apply_status(
        self,
        *,
        work_order_id: UUID,
        expected_status: WorkOrderStatus,
        new_status: WorkOrderStatus,
    ) -> datetime | None:
        self.applied.append((expected_status, new_status))
        if self.conflict:
            return None
        return UPDATED_AT


def build_tool(
    status: WorkOrderStatus | None,
    code: str = "WO-1001",
) -> tuple[ToolDefinition, FakeWorkOrderStatusStore]:
    snapshot = (
        None
        if status is None
        else WorkOrderStatusSnapshot(id=WORK_ORDER_ID, code=code, status=status)
    )
    store = FakeWorkOrderStatusStore(snapshot)
    return build_write_work_order_status_tool(lambda: store), store


async def invoke(tool: ToolDefinition, payload: dict[str, Any]) -> dict[str, Any]:
    return await tool.handler(payload)


async def test_tool_is_approval_gated_and_rate_limited() -> None:
    tool, _ = build_tool(WorkOrderStatus.OPEN)

    assert tool.name == "write_work_order_status"
    assert tool.name.startswith("write_")
    assert tool.requires_approval is True
    assert tool.approval_scope == "write"
    assert tool.required_permission == Permission.WORK_ORDERS_CHANGE_STATUS
    assert tool.max_retries == 0
    assert tool.rate_limit is not None
    assert tool.rate_limit.max_calls == 3


async def test_allowed_transition_updates_status() -> None:
    tool, store = build_tool(WorkOrderStatus.OPEN)

    result = await invoke(tool, {"work_order_code": "WO-1001", "target_status": "in_progress"})

    assert store.applied == [(WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS)]
    assert result == {
        "tool_name": "write_work_order_status",
        "succeeded": True,
        "work_order_code": "WO-1001",
        "previous_status": "open",
        "current_status": "in_progress",
        "changed": True,
        "updated_at": UPDATED_AT.isoformat(),
        "allowed_next_statuses": ["cancelled", "completed", "open"],
        "error_code": None,
        "error_message": None,
    }


async def test_illegal_transition_is_rejected_without_writing() -> None:
    tool, store = build_tool(WorkOrderStatus.PENDING)

    result = await invoke(tool, {"work_order_code": "WO-1001", "target_status": "completed"})

    assert store.applied == []
    assert result["succeeded"] is False
    assert result["error_code"] == "invalid_work_order_status_transition"
    assert result["current_status"] == "pending"
    assert result["allowed_next_statuses"] == ["cancelled", "open"]


async def test_terminal_status_cannot_be_changed() -> None:
    tool, store = build_tool(WorkOrderStatus.COMPLETED)

    result = await invoke(tool, {"work_order_code": "WO-1001", "target_status": "open"})

    assert store.applied == []
    assert result["error_code"] == "work_order_status_is_terminal"
    assert result["allowed_next_statuses"] == []


async def test_completing_without_reason_is_rejected() -> None:
    tool, store = build_tool(WorkOrderStatus.IN_PROGRESS)

    result = await invoke(tool, {"work_order_code": "WO-1001", "target_status": "completed"})

    assert store.applied == []
    assert result["error_code"] == "work_order_status_reason_required"


async def test_completing_with_reason_succeeds() -> None:
    tool, store = build_tool(WorkOrderStatus.IN_PROGRESS)

    result = await invoke(
        tool,
        {
            "work_order_code": "WO-1001",
            "target_status": "completed",
            "reason": "bearing replaced and line restarted",
        },
    )

    assert store.applied == [(WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETED)]
    assert result["succeeded"] is True
    assert result["current_status"] == "completed"


async def test_setting_the_same_status_is_a_no_op() -> None:
    tool, store = build_tool(WorkOrderStatus.IN_PROGRESS)

    result = await invoke(tool, {"work_order_code": "WO-1001", "target_status": "in_progress"})

    assert store.applied == []
    assert result["succeeded"] is True
    assert result["changed"] is False
    assert result["updated_at"] is None


async def test_unknown_work_order_is_rejected() -> None:
    tool, store = build_tool(None)

    result = await invoke(tool, {"work_order_code": "WO-9999", "target_status": "open"})

    assert store.applied == []
    assert result["error_code"] == "work_order_not_found"
    assert result["current_status"] is None


async def test_concurrent_status_change_is_reported_as_conflict() -> None:
    tool, store = build_tool(WorkOrderStatus.OPEN)
    store.conflict = True

    result = await invoke(tool, {"work_order_code": "WO-1001", "target_status": "in_progress"})

    assert result["succeeded"] is False
    assert result["error_code"] == "work_order_status_conflict"


async def test_unknown_status_and_extra_arguments_are_rejected() -> None:
    tool, _ = build_tool(WorkOrderStatus.OPEN)

    with pytest.raises(ValidationError):
        await invoke(tool, {"work_order_code": "WO-1001", "target_status": "archived"})

    with pytest.raises(ValidationError):
        await invoke(
            tool,
            {"work_order_code": "WO-1001", "target_status": "open", "force": True},
        )
