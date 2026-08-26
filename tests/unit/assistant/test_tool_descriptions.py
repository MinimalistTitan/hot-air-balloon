import json
from collections.abc import Callable
from typing import cast

from app.modules.assistant.domain.ports.web_search import WebSearchPort
from app.modules.assistant.infrastructure.web_search.tool import build_web_search_tool
from app.modules.operations.application.ports import WorkOrderStatusStore
from app.modules.operations.infrastructure.repositories.operations import OperationsRepository
from app.modules.operations.infrastructure.tools.tool_builder import (
    build_get_asset_status_tool,
    build_get_maintenance_tickets_tool,
    build_get_production_schedule_tool,
    build_get_spare_parts_availability_tool,
    build_get_work_orders_tool,
)
from app.modules.operations.infrastructure.tools.write_work_order_status_tool import (
    build_write_work_order_status_tool,
)


def _repository_factory() -> Callable[[], OperationsRepository]:
    return cast(Callable[[], OperationsRepository], lambda: None)


def test_operational_tool_descriptions_define_positive_and_negative_boundaries() -> None:
    repository_factory = _repository_factory()
    tools = {
        tool.name: tool
        for tool in (
            build_get_work_orders_tool(repository_factory),
            build_get_asset_status_tool(repository_factory),
            build_get_maintenance_tickets_tool(repository_factory),
            build_get_spare_parts_availability_tool(repository_factory),
            build_get_production_schedule_tool(repository_factory),
        )
    }

    assert "show open work orders" in tools["get_work_orders"].description
    assert "Do not use for due-soonest" in tools["get_work_orders"].description
    assert "Do not use for work orders" in tools["get_asset_status"].description
    assert "Do not use for all work orders" in tools["get_maintenance_tickets"].description
    assert "parts availability or inventory" in tools["get_spare_parts_availability"].description
    assert "Use for due-soonest" in tools["get_production_schedule"].description
    assert all("Read-only" in tool.description for tool in tools.values())

    work_order_schema = json.dumps(tools["get_work_orders"].input_model.model_json_schema())
    for status in ("pending", "open", "in_progress", "completed", "cancelled"):
        assert status in work_order_schema


def test_mutating_tool_description_requires_explicit_user_intent() -> None:
    store_factory = cast(Callable[[], WorkOrderStatusStore], lambda: None)
    tool = build_write_work_order_status_tool(store_factory)

    assert "only when the user explicitly requests" in tool.description
    assert "Never use for definitions" in tool.description
    assert "Mutating and approval-gated" in tool.description


def test_web_search_description_excludes_internal_erp_data() -> None:
    tool = build_web_search_tool(cast(WebSearchPort, object()))

    assert "current or externally verifiable information" in tool.description
    assert "Do not use for internal ERP work orders" in tool.description
