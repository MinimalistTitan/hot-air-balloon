from __future__ import annotations
from fastapi import APIRouter
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from typing import Annotated

from app.container import get_container
from app.modules.operations.application.operation_services import OperationsService
from app.modules.operations.wiring import OperationsModule

router = APIRouter(prefix="/operations", tags=["operations"])

def get_operations_module(request: Request) -> OperationsModule:
    module = get_container(request).operations
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operations module is not configured",
        )
    return module


def get_operations_service(
    module: Annotated[OperationsModule, Depends(get_operations_module)],
) -> OperationsService:
    return module.service


@router.get("/work-orders")
async def get_work_orders(
    service: Annotated[OperationsService, Depends(get_operations_service)],
    site_code: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=10, ge=1, le=100),
) -> list[dict[str, object]]:
    return await service.get_work_orders(
        site_code=site_code,
        status=status_filter,
        limit=limit,
    )


@router.get("/asset-status")
async def get_asset_status(
    service: Annotated[OperationsService, Depends(get_operations_service)],
    site_code: str | None = None,
) -> list[dict[str, object]]:
    return await service.get_asset_status(site_code=site_code)


@router.get("/maintenance-tickets")
async def get_maintenance_tickets(
    service: Annotated[OperationsService, Depends(get_operations_service)],
    site_code: str | None = None,
    limit: int = Query(default=10, ge=1, le=100),
) -> list[dict[str, object]]:
    return await service.get_maintenance_tickets(site_code=site_code, limit=limit)


@router.get("/spare-parts-availability")
async def get_spare_parts_availability(
    service: Annotated[OperationsService, Depends(get_operations_service)],
    site_code: str | None = None,
    limit: int = Query(default=10, ge=1, le=100),
) -> list[dict[str, object]]:
    return await service.get_spare_parts_availability(site_code=site_code, limit=limit)


@router.get("/production-schedule")
async def get_production_schedule(
    service: Annotated[OperationsService, Depends(get_operations_service)],
    site_code: str | None = None,
    limit: int = Query(default=10, ge=1, le=100),
) -> list[dict[str, object]]:
    return await service.get_production_schedule(site_code=site_code, limit=limit)