from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.modules.operations.infrastructure.repositories.operations import OperationsRepository


@dataclass(slots=True)
class OperationsService:
    repository_factory: Callable[[], OperationsRepository]

    async def get_work_orders(
        self,
        *,
        site_code: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        repository = self.repository_factory()
        return await repository.list_work_orders(
            site_code=site_code,
            status=status,
            limit=limit,
        )

    async def get_asset_status(
        self,
        *,
        site_code: str | None = None,
    ) -> list[dict[str, object]]:
        repository = self.repository_factory()
        return await repository.get_asset_status(site_code=site_code)

    async def get_maintenance_tickets(
        self,
        *,
        site_code: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        repository = self.repository_factory()
        return await repository.list_maintenance_tickets(
            site_code=site_code,
            limit=limit,
        )

    async def get_spare_parts_availability(
        self,
        *,
        site_code: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        repository = self.repository_factory()
        return await repository.list_spare_parts_availability(
            site_code=site_code,
            limit=limit,
        )

    async def get_production_schedule(
        self,
        *,
        site_code: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        repository = self.repository_factory()
        return await repository.list_production_schedule(
            site_code=site_code,
            limit=limit,
        )