from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.operations.domain.manufacturing_maintenance.work_order_status import (
    WorkOrderStatus,
)


@dataclass(frozen=True, slots=True)
class WorkOrderStatusSnapshot:
    id: UUID
    code: str
    status: WorkOrderStatus


class WorkOrderStatusStore(Protocol):
    async def find_status_by_code(self, work_order_code: str | None = None) -> WorkOrderStatusSnapshot | None: ...

    async def find_status_by_id(
            self,
            work_order_id: UUID,
            *,
            site_code: str | None = None,
        ) -> WorkOrderStatusSnapshot | None: ...

    async def apply_status(
        self,
        *,
        work_order_id: UUID,
        expected_status: WorkOrderStatus,
        new_status: WorkOrderStatus,
    ) -> datetime | None: ...
