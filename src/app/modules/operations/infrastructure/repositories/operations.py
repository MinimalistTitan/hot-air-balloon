from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.operations.infrastructure.manufacturing_maintenance.models import (
    AssetRecord,
    SiteRecord,
    SparePartRecord,
    WorkOrderRecord,
)
from app.modules.user.application.authorization_policy import AuthorizationPolicy
from app.modules.user.domain.authorization import Permission


class OperationsRepository:
    def __init__(
        self,
        session: AsyncSession,
        authorization_policy: AuthorizationPolicy | None = None,
        current_user_id: UUID | None = None,
    ) -> None:
        self._session = session
        self._authorization_policy = authorization_policy
        self._current_user_id = current_user_id

    async def list_work_orders(
        self,
        *,
        site_code: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        if self._authorization_policy and self._current_user_id and site_code:
            await self._authorization_policy.require_permission(
                self._current_user_id,
                Permission.WORK_ORDERS_READ,
                site_code=site_code,
            )

        query = select(WorkOrderRecord).options(selectinload(WorkOrderRecord.site))

        if site_code is not None:
            query = query.join(SiteRecord, WorkOrderRecord.site_id == SiteRecord.id).where(
                SiteRecord.code == site_code
            )

        if status is not None:
            query = query.where(WorkOrderRecord.status == status)

        query = query.order_by(WorkOrderRecord.created_at.desc()).limit(limit)

        rows = (await self._session.execute(query)).scalars().all()
        return [
            {
                "id": str(row.id),
                "site_id": str(row.site_id),
                "site_code": row.site.code,
                "asset_id": str(row.asset_id),
                "code": row.code,
                "title": row.title,
                "description": row.description,
                "priority": row.priority,
                "status": row.status,
                "work_type": row.work_type,
                "due_at": row.due_at.isoformat() if row.due_at else None,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
            }
            for row in rows
        ]

    async def get_asset_status(
        self,
        *,
        site_code: str | None = None,
    ) -> list[dict[str, object]]:
        if self._authorization_policy and self._current_user_id and site_code:
            await self._authorization_policy.require_permission(
                self._current_user_id,
                Permission.ASSETS_READ,
                site_code=site_code,
            )

        query = select(AssetRecord).options(selectinload(AssetRecord.site))

        if site_code is not None:
            query = query.join(SiteRecord, AssetRecord.site_id == SiteRecord.id).where(
                SiteRecord.code == site_code
            )

        query = query.order_by(AssetRecord.code.asc())

        rows = (await self._session.execute(query)).scalars().all()
        return [
            {
                "id": str(row.id),
                "code": row.code,
                "name": row.name,
                "category": row.category,
                "criticality": row.criticality,
                "status": row.status,
                "site_code": row.site.code if row.site else None,
            }
            for row in rows
        ]

    async def list_maintenance_tickets(
        self,
        *,
        site_code: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        query = (
            select(WorkOrderRecord)
            .options(
                selectinload(WorkOrderRecord.asset),
                selectinload(WorkOrderRecord.site),
            )
            .where(WorkOrderRecord.status.in_(["open", "in_progress", "pending"]))
        )

        if site_code is not None:
            query = query.join(SiteRecord, WorkOrderRecord.site_id == SiteRecord.id).where(
                SiteRecord.code == site_code
            )

        query = query.order_by(
            WorkOrderRecord.priority.desc(),
            WorkOrderRecord.created_at.desc(),
        ).limit(limit)

        rows = (await self._session.execute(query)).scalars().all()
        return [
            {
                "ticket_id": str(row.id),
                "site_code": row.site.code,
                "code": row.code,
                "title": row.title,
                "asset_code": row.asset.code if row.asset else None,
                "priority": row.priority,
                "status": row.status,
                "due_at": row.due_at.isoformat() if row.due_at else None,
                "work_type": row.work_type,
            }
            for row in rows
        ]

    async def list_spare_parts_availability(
        self,
        *,
        site_code: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        query = select(SparePartRecord).options(selectinload(SparePartRecord.site))

        if site_code is not None:
            query = query.join(SiteRecord, SparePartRecord.site_id == SiteRecord.id).where(
                SiteRecord.code == site_code
            )

        query = query.order_by(SparePartRecord.code.asc()).limit(limit)

        rows = (await self._session.execute(query)).scalars().all()
        return [
            {
                "part_id": str(row.id),
                "site_code": row.site.code,
                "code": row.code,
                "name": row.name,
                "uom": row.uom,
                "on_hand_qty": row.on_hand_qty,
                "reorder_point": row.reorder_point,
                "critical": row.critical,
                "below_reorder": row.on_hand_qty < row.reorder_point,
            }
            for row in rows
        ]

    async def list_production_schedule(
        self,
        *,
        site_code: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        query = (
            select(WorkOrderRecord)
            .options(
                selectinload(WorkOrderRecord.asset),
                selectinload(WorkOrderRecord.site),
            )
            .where(WorkOrderRecord.due_at.isnot(None))
        )

        if site_code is not None:
            query = query.join(SiteRecord, WorkOrderRecord.site_id == SiteRecord.id).where(
                SiteRecord.code == site_code
            )

        query = query.order_by(WorkOrderRecord.due_at.asc()).limit(limit)

        rows = (await self._session.execute(query)).scalars().all()
        return [
            {
                "id": str(row.id),
                "site_code": row.site.code,
                "code": row.code,
                "title": row.title,
                "asset_code": row.asset.code if row.asset else None,
                "work_type": row.work_type,
                "status": row.status,
                "due_at": row.due_at.isoformat() if row.due_at else None,
                "priority": row.priority,
            }
            for row in rows
        ]
