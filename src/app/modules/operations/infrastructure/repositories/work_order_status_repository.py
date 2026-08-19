from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.operations.application.ports import WorkOrderStatusSnapshot
from app.modules.operations.domain.manufacturing_maintenance.work_order_status import (
    WorkOrderStatus,
)
from app.modules.operations.infrastructure.manufacturing_maintenance.models import WorkOrderRecord


class WorkOrderStatusRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_status_by_code(self, work_order_code: str) -> WorkOrderStatusSnapshot | None:
        query = select(WorkOrderRecord).where(WorkOrderRecord.code == work_order_code)
        row = (await self._session.execute(query)).scalar_one_or_none()
        if row is None:
            return None

        return WorkOrderStatusSnapshot(
            id=row.id,
            code=row.code,
            status=WorkOrderStatus(row.status),
        )

    async def apply_status(
        self,
        *,
        work_order_id: UUID,
        expected_status: WorkOrderStatus,
        new_status: WorkOrderStatus,
    ) -> datetime | None:
        statement = (
            update(WorkOrderRecord)
            .where(
                WorkOrderRecord.id == work_order_id,
                WorkOrderRecord.status == expected_status.value,
            )
            .values(status=new_status.value)
            .returning(WorkOrderRecord.updated_at)
        )

        updated_at = (await self._session.execute(statement)).scalar_one_or_none()
        if updated_at is None:
            await self._session.rollback()
            return None

        await self._session.commit()
        return updated_at
