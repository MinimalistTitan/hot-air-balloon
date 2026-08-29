from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assistant.tool_gateway.domain import AssistantToolRegistration, ToolDefinition, ToolRateLimit
from app.modules.operations.domain.manufacturing_maintenance.work_order_status import (
    WorkOrderStatus,
)
from app.modules.operations.infrastructure.repositories.operations import OperationsRepository
from app.modules.operations.infrastructure.tools.result_adapters import ASSETS_ADAPTER, MAINTENANCE_TICKETS_ADAPTER, PRODUCTION_SCHEDULE_ADAPTER, SPARE_PARTS_ADAPTER, WORK_ORDERS_ADAPTER
from app.modules.user.domain.authorization import Permission

READ_TOOL_RATE_LIMIT = ToolRateLimit(max_calls=30, window_seconds=60)

GET_WORK_ORDERS_DESCRIPTION = (
    "List existing ERP work orders, optionally filtered by exact site_code and status, with a "
    "maximum limit of 1-100. Use for requests such as 'show open work orders at PLANT-HCM'. "
    "Do not use for due-soonest or production-schedule requests, maintenance-ticket queues, "
    "definitions, status changes, or lookup by one exact work-order code/UUID. Read-only."
)
GET_ASSET_STATUS_DESCRIPTION = (
    "List current ERP asset status and criticality, optionally for one exact site_code. Use only "
    "for asset condition/status requests. Do not use for work orders, maintenance tickets, spare "
    "parts, production schedules, explanations, or any mutation. Read-only."
)
GET_MAINTENANCE_TICKETS_DESCRIPTION = (
    "List maintenance tickets whose status is pending, open, or in_progress, optionally filtered "
    "by exact site_code and limited to 1-100 rows. Use for maintenance-ticket queue requests. "
    "Do not use for all work orders, due-date schedules, asset status, definitions, or changes. "
    "Read-only."
)
GET_SPARE_PARTS_AVAILABILITY_DESCRIPTION = (
    "List ERP spare-part stock, reorder levels, and below-reorder indicators, optionally filtered "
    "by exact site_code and limited to 1-100 rows. Use only for parts availability or inventory "
    "requests. Do not use for work orders, assets, schedules, explanations, or stock mutations. "
    "Read-only."
)
GET_PRODUCTION_SCHEDULE_DESCRIPTION = (
    "List due-dated work orders ordered by earliest due_at, optionally filtered by exact "
    "site_code and limited to 1-100 rows. Use for due-soonest, upcoming, deadline, or production "
    "schedule requests. Do not use for generic open-work-order lists, maintenance tickets, "
    "definitions, or status changes. Read-only."
)


class GetWorkOrdersInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    site_code: str | None = Field(default=None, description="Exact ERP site code from the request")
    status: WorkOrderStatus | None = Field(
        default=None,
        description="Exact requested status: pending, open, in_progress, completed, or cancelled",
    )
    limit: int = Field(default=10, ge=1, le=100)


class WorkOrderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    site_id: str
    site_code: str
    asset_id: str
    code: str
    title: str
    description: str
    priority: str
    status: str
    work_type: str
    due_at: str | None
    created_at: str
    updated_at: str


class GetWorkOrdersOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = "get_work_orders"
    work_orders: list[WorkOrderItem]


class GetAssetStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_code: str | None = Field(default=None, description="Exact ERP site code from the request")


class AssetStatusItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    name: str
    category: str
    criticality: str
    status: str
    site_code: str | None


class GetAssetStatusOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = "get_asset_status"
    assets: list[AssetStatusItem]


class GetMaintenanceTicketsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_code: str | None = Field(default=None, description="Exact ERP site code from the request")
    limit: int = Field(default=10, ge=1, le=100)


class MaintenanceTicketItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    site_code: str
    code: str
    title: str
    asset_code: str | None
    priority: str
    status: str
    due_at: str | None
    work_type: str


class GetMaintenanceTicketsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = "get_maintenance_tickets"
    tickets: list[MaintenanceTicketItem]


class GetSparePartsAvailabilityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_code: str | None = Field(default=None, description="Exact ERP site code from the request")
    limit: int = Field(default=10, ge=1, le=100)


class SparePartItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_id: str
    site_code: str
    code: str
    name: str
    uom: str
    on_hand_qty: int
    reorder_point: int
    critical: bool
    below_reorder: bool


class GetSparePartsAvailabilityOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = "get_spare_parts_availability"
    spare_parts: list[SparePartItem]


class GetProductionScheduleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_code: str | None = Field(default=None, description="Exact ERP site code from the request")
    limit: int = Field(default=10, ge=1, le=100)


class ProductionScheduleItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    site_code: str
    code: str
    title: str
    asset_code: str | None
    work_type: str
    status: str
    due_at: str | None
    priority: str


class GetProductionScheduleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = "get_production_schedule"
    schedule: list[ProductionScheduleItem]


def build_get_work_orders_tool(
    repository_factory: Callable[[], OperationsRepository],
) -> AssistantToolRegistration:
    async def invoke(payload: dict[str, Any]) -> dict[str, Any]:
        data = GetWorkOrdersInput.model_validate(payload)
        repository = repository_factory()
        work_orders = await repository.list_work_orders(
            site_code=data.site_code,
            status=data.status.value if data.status is not None else None,
            limit=data.limit,
        )
        output = GetWorkOrdersOutput(
            work_orders=[WorkOrderItem.model_validate(item) for item in work_orders]
        )
        return output.model_dump(mode="json")

    return AssistantToolRegistration(
        definition=ToolDefinition(
            name="get_work_orders",
            description=GET_WORK_ORDERS_DESCRIPTION,
            input_model=GetWorkOrdersInput,
            output_model=GetWorkOrdersOutput,
            handler=invoke,
            required_permission=Permission.WORK_ORDERS_READ,
            site_code_field="site_code",
            rate_limit=READ_TOOL_RATE_LIMIT,
        ),
        result_adapter=WORK_ORDERS_ADAPTER,
    )


def build_get_asset_status_tool(
    repository_factory: Callable[[], OperationsRepository],
) -> AssistantToolRegistration:
    async def invoke(payload: dict[str, Any]) -> dict[str, Any]:
        data = GetAssetStatusInput.model_validate(payload)
        repository = repository_factory()
        assets = await repository.get_asset_status(site_code=data.site_code)
        output = GetAssetStatusOutput(
            assets=[AssetStatusItem.model_validate(item) for item in assets]
        )
        return output.model_dump(mode="json")

    return AssistantToolRegistration(
        definition=ToolDefinition(
            name="get_asset_status",
            description=GET_ASSET_STATUS_DESCRIPTION,
            input_model=GetAssetStatusInput,
            output_model=GetAssetStatusOutput,
            handler=invoke,
            required_permission=Permission.ASSETS_READ,
            site_code_field="site_code",
            rate_limit=READ_TOOL_RATE_LIMIT,
        ),
        result_adapter=ASSETS_ADAPTER,
    )


def build_get_maintenance_tickets_tool(
    repository_factory: Callable[[], OperationsRepository],
) -> AssistantToolRegistration:
    async def invoke(payload: dict[str, Any]) -> dict[str, Any]:
        data = GetMaintenanceTicketsInput.model_validate(payload)
        repository = repository_factory()
        tickets = await repository.list_maintenance_tickets(
            site_code=data.site_code,
            limit=data.limit,
        )
        output = GetMaintenanceTicketsOutput(
            tickets=[MaintenanceTicketItem.model_validate(item) for item in tickets]
        )
        return output.model_dump(mode="json")

    return AssistantToolRegistration(
        definition=ToolDefinition(
            name="get_maintenance_tickets",
            description=GET_MAINTENANCE_TICKETS_DESCRIPTION,
            input_model=GetMaintenanceTicketsInput,
            output_model=GetMaintenanceTicketsOutput,
            handler=invoke,
            required_permission=Permission.MAINTENANCE_TICKETS_READ,
            site_code_field="site_code",
            rate_limit=READ_TOOL_RATE_LIMIT,
        ),
        result_adapter=MAINTENANCE_TICKETS_ADAPTER,
    )


def build_get_spare_parts_availability_tool(
    repository_factory: Callable[[], OperationsRepository],
) -> AssistantToolRegistration:
    async def invoke(payload: dict[str, Any]) -> dict[str, Any]:
        data = GetSparePartsAvailabilityInput.model_validate(payload)
        repository = repository_factory()
        spare_parts = await repository.list_spare_parts_availability(
            site_code=data.site_code,
            limit=data.limit,
        )
        output = GetSparePartsAvailabilityOutput(
            spare_parts=[SparePartItem.model_validate(item) for item in spare_parts]
        )
        return output.model_dump(mode="json")

    return AssistantToolRegistration(
        definition=ToolDefinition(
            name="get_spare_parts_availability",
            description=GET_SPARE_PARTS_AVAILABILITY_DESCRIPTION,
            input_model=GetSparePartsAvailabilityInput,
            output_model=GetSparePartsAvailabilityOutput,
            handler=invoke,
            required_permission=Permission.SPARE_PARTS_READ,
            site_code_field="site_code",
            rate_limit=READ_TOOL_RATE_LIMIT,
        ),
        result_adapter=SPARE_PARTS_ADAPTER,
    )


def build_get_production_schedule_tool(
    repository_factory: Callable[[], OperationsRepository],
) -> AssistantToolRegistration:
    async def invoke(payload: dict[str, Any]) -> dict[str, Any]:
        data = GetProductionScheduleInput.model_validate(payload)
        repository = repository_factory()
        schedule = await repository.list_production_schedule(
            site_code=data.site_code,
            limit=data.limit,
        )
        output = GetProductionScheduleOutput(
            schedule=[ProductionScheduleItem.model_validate(item) for item in schedule]
        )
        return output.model_dump(mode="json")

    return AssistantToolRegistration(
        definition=ToolDefinition(
            name="get_production_schedule",
            description=GET_PRODUCTION_SCHEDULE_DESCRIPTION,
            input_model=GetProductionScheduleInput,
            output_model=GetProductionScheduleOutput,
            handler=invoke,
            required_permission=Permission.PRODUCTION_SCHEDULE_READ,
            site_code_field="site_code",
            rate_limit=READ_TOOL_RATE_LIMIT,
        ),
        result_adapter=PRODUCTION_SCHEDULE_ADAPTER,
    )
