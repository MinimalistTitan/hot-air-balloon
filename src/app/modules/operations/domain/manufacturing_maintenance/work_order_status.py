from __future__ import annotations

from enum import StrEnum


class WorkOrderStatus(StrEnum):
    PENDING = "pending"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


_ALLOWED_TRANSITIONS: dict[WorkOrderStatus, frozenset[WorkOrderStatus]] = {
    WorkOrderStatus.PENDING: frozenset({WorkOrderStatus.OPEN, WorkOrderStatus.CANCELLED}),
    WorkOrderStatus.OPEN: frozenset({WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED}),
    WorkOrderStatus.IN_PROGRESS: frozenset(
        {WorkOrderStatus.OPEN, WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED}
    ),
    WorkOrderStatus.COMPLETED: frozenset(),
    WorkOrderStatus.CANCELLED: frozenset(),
}

_STATUSES_REQUIRING_REASON: frozenset[WorkOrderStatus] = frozenset(
    {WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED}
)


def allowed_next_statuses(current: WorkOrderStatus) -> tuple[WorkOrderStatus, ...]:
    return tuple(sorted(_ALLOWED_TRANSITIONS[current], key=lambda status: status.value))


def is_terminal(status: WorkOrderStatus) -> bool:
    return not _ALLOWED_TRANSITIONS[status]


def is_transition_allowed(current: WorkOrderStatus, target: WorkOrderStatus) -> bool:
    return target in _ALLOWED_TRANSITIONS[current]


def requires_reason(target: WorkOrderStatus) -> bool:
    return target in _STATUSES_REQUIRING_REASON
