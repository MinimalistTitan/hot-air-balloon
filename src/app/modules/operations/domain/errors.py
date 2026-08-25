from __future__ import annotations

from app.modules.operations.domain.manufacturing_maintenance.work_order_status import (
    WorkOrderStatus,
    allowed_next_statuses,
)
from app.shared.domain.errors import DomainError


class WorkOrderNotFoundError(DomainError):
    code = "work_order_not_found"

    def __init__(self, work_order_code: str | None = None) -> None:
        super().__init__(f"work order not found: {work_order_code}")
        self.work_order_code = work_order_code


class WorkOrderTerminalStatusError(DomainError):
    code = "work_order_status_is_terminal"

    def __init__(self, work_order_code: str, current: WorkOrderStatus) -> None:
        super().__init__(
            f"work order {work_order_code} is {current.value} and can no longer change status"
        )
        self.work_order_code = work_order_code
        self.current = current


class InvalidWorkOrderStatusTransitionError(DomainError):
    code = "invalid_work_order_status_transition"

    def __init__(
        self,
        work_order_code: str,
        current: WorkOrderStatus,
        target: WorkOrderStatus,
    ) -> None:
        allowed = ", ".join(status.value for status in allowed_next_statuses(current))
        super().__init__(
            f"work order {work_order_code} cannot move from {current.value} to {target.value}; "
            f"allowed next statuses: {allowed or 'none'}"
        )
        self.work_order_code = work_order_code
        self.current = current
        self.target = target


class WorkOrderStatusConflictError(DomainError):
    code = "work_order_status_conflict"

    def __init__(self, work_order_code: str, expected: WorkOrderStatus) -> None:
        super().__init__(
            f"work order {work_order_code} was no longer {expected.value} when the update ran; "
            "re-read the current status and retry"
        )
        self.work_order_code = work_order_code
        self.expected = expected


class WorkOrderStatusReasonRequiredError(DomainError):
    code = "work_order_status_reason_required"

    def __init__(self, work_order_code: str, target: WorkOrderStatus) -> None:
        super().__init__(
            f"moving work order {work_order_code} to {target.value} requires a reason"
        )
        self.work_order_code = work_order_code
        self.target = target
