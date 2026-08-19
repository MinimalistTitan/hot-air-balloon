from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.modules.operations.application.ports import WorkOrderStatusStore
from app.modules.operations.domain.errors import (
    InvalidWorkOrderStatusTransitionError,
    WorkOrderNotFoundError,
    WorkOrderStatusConflictError,
    WorkOrderStatusReasonRequiredError,
    WorkOrderTerminalStatusError,
)
from app.modules.operations.domain.manufacturing_maintenance.work_order_status import (
    WorkOrderStatus,
    is_terminal,
    is_transition_allowed,
    requires_reason,
)


@dataclass(frozen=True, slots=True)
class ChangeWorkOrderStatusCommand:
    work_order_code: str
    target_status: WorkOrderStatus
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ChangeWorkOrderStatusResult:
    work_order_code: str
    previous_status: WorkOrderStatus
    current_status: WorkOrderStatus
    changed: bool
    updated_at: datetime | None


@dataclass(slots=True)
class ChangeWorkOrderStatus:
    store: WorkOrderStatusStore

    async def execute(self, command: ChangeWorkOrderStatusCommand) -> ChangeWorkOrderStatusResult:
        snapshot = await self.store.find_status_by_code(command.work_order_code)
        if snapshot is None:
            raise WorkOrderNotFoundError(command.work_order_code)

        current = snapshot.status
        target = command.target_status

        if current == target:
            return ChangeWorkOrderStatusResult(
                work_order_code=snapshot.code,
                previous_status=current,
                current_status=current,
                changed=False,
                updated_at=None,
            )

        if is_terminal(current):
            raise WorkOrderTerminalStatusError(snapshot.code, current)

        if not is_transition_allowed(current, target):
            raise InvalidWorkOrderStatusTransitionError(snapshot.code, current, target)

        if requires_reason(target) and not command.reason:
            raise WorkOrderStatusReasonRequiredError(snapshot.code, target)

        updated_at = await self.store.apply_status(
            work_order_id=snapshot.id,
            expected_status=current,
            new_status=target,
        )
        if updated_at is None:
            raise WorkOrderStatusConflictError(snapshot.code, current)

        return ChangeWorkOrderStatusResult(
            work_order_code=snapshot.code,
            previous_status=current,
            current_status=target,
            changed=True,
            updated_at=updated_at,
        )
