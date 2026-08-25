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
from app.modules.operations.infrastructure.manufacturing_maintenance.models.models import SiteRecord


def _snapshot(row: WorkOrderRecord) -> WorkOrderStatusSnapshot:
    return WorkOrderStatusSnapshot(
        id=row.id,
        code=row.code,
        status=WorkOrderStatus(row.status),
    )

class WorkOrderStatusRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_status_by_id(
        self,
        work_order_id: UUID,
        *,
        site_code: str | None = None,
    ) -> WorkOrderStatusSnapshot | None:
        query = select(WorkOrderRecord).where(
            WorkOrderRecord.id == work_order_id
        )

        if site_code is not None:
            query = query.join(
                SiteRecord,
                WorkOrderRecord.site_id == SiteRecord.id,
            ).where(SiteRecord.code == site_code)

        row = (await self._session.execute(query)).scalar_one_or_none()
        return _snapshot(row) if row is not None else None

    async def find_status_by_code(
        self,
        work_order_code: str,
        *,
        site_code: str | None = None,
    ) -> list[WorkOrderStatusSnapshot]:
        query = select(WorkOrderRecord).where(
            WorkOrderRecord.code == work_order_code
        )

        if site_code is not None:
            query = query.join(
                SiteRecord,
                WorkOrderRecord.site_id == SiteRecord.id,
            ).where(SiteRecord.code == site_code)

        rows = (await self._session.execute(query)).scalars().all()
        return [_snapshot(row) for row in rows]

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
