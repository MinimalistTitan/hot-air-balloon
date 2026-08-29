from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.core.database.database import SessionFactory
from app.modules.assistant.tool_gateway.domain import AssistantToolRegistration
from app.modules.operations.application.operation_services import OperationsService
from app.modules.operations.application.ports import WorkOrderStatusStore
from app.modules.operations.infrastructure.repositories.operations import OperationsRepository
from app.modules.operations.infrastructure.repositories.work_order_status_repository import (
    WorkOrderStatusRepository,
)
from app.modules.operations.infrastructure.tools import (
    build_get_asset_status_tool,
    build_get_maintenance_tickets_tool,
    build_get_production_schedule_tool,
    build_get_spare_parts_availability_tool,
    build_get_work_orders_tool,
    build_write_work_order_status_tool,
)


@dataclass(frozen=True, slots=True)
class OperationsModule:
    service: OperationsService
    get_work_orders_tool: AssistantToolRegistration
    get_asset_status_tool: AssistantToolRegistration
    get_maintenance_tickets_tool: AssistantToolRegistration
    get_spare_parts_availability_tool: AssistantToolRegistration
    get_production_schedule_tool: AssistantToolRegistration
    write_work_order_status_tool: AssistantToolRegistration

    @property
    def tools(self) -> tuple[AssistantToolRegistration, ...]:
        return (
            self.get_work_orders_tool,
            self.get_asset_status_tool,
            self.get_maintenance_tickets_tool,
            self.get_spare_parts_availability_tool,
            self.get_production_schedule_tool,
            self.write_work_order_status_tool,
        )

def build_operations_module(
    settings: Settings,
    session_factory: SessionFactory,
) -> OperationsModule:
    def repository_factory() -> OperationsRepository:
        return OperationsRepository(session_factory())

    def work_order_status_store_factory() -> WorkOrderStatusStore:
        return WorkOrderStatusRepository(session_factory())

    service = OperationsService(repository_factory=repository_factory)

    return OperationsModule(
        service=service,
        get_work_orders_tool=build_get_work_orders_tool(repository_factory),
        get_asset_status_tool=build_get_asset_status_tool(repository_factory),
        get_maintenance_tickets_tool=build_get_maintenance_tickets_tool(repository_factory),
        get_spare_parts_availability_tool=build_get_spare_parts_availability_tool(repository_factory),
        get_production_schedule_tool=build_get_production_schedule_tool(repository_factory),
        write_work_order_status_tool=build_write_work_order_status_tool(
            work_order_status_store_factory
        ),
    )
