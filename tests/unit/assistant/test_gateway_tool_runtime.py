from uuid import UUID

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database.database import Base, create_session_factory
from app.modules.assistant.infrastructure.tool_gateway.models import (
    AssistantToolAuditRecord,
    AssistantToolTraceEvent,
)
from app.modules.assistant.infrastructure.tool_runtime.gateway_runtime import (
    GatewayToolRuntime,
)
from app.modules.assistant.tool_gateway.domain import ToolDefinition
from app.modules.assistant.tool_gateway.registry import ToolRegistry
from app.modules.user.domain.authorization import (
    AuthorizationContext,
    Permission,
    RoleName,
)


class AssetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_code: str


class AssetOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = "get_asset_status"
    status: str


class HandlerSpy:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def __call__(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        return {"tool_name": "get_asset_status", "status": "available"}


def authorization_context(site_codes: frozenset[str]) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=UUID("11111111-1111-1111-1111-111111111111"),
        roles=frozenset({RoleName.MAINTENANCE_TECHNICIAN}),
        site_codes=site_codes,
    )


async def test_gateway_runtime_enforces_authorization_and_persists_audit_trace() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    handler = HandlerSpy()
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="get_asset_status",
            description="Get asset status",
            input_model=AssetInput,
            output_model=AssetOutput,
            handler=handler,
            required_permission=Permission.ASSETS_READ,
            site_code_field="site_code",
        )
    )
    runtime = GatewayToolRuntime(
        registry=registry,
        session_factory=create_session_factory(engine),
    )

    descriptors = await runtime.list_tools()
    assert [(tool.name, tool.description) for tool in descriptors] == [
        ("get_asset_status", "Get asset status")
    ]

    result = await runtime.invoke(
        "get_asset_status",
        {"site_code": "HN-01"},
        authorization_context(frozenset({"HN-01"})),
    )

    assert result["status"] == "success"
    assert handler.calls == [{"site_code": "HN-01"}]

    with pytest.raises(PermissionError, match="tool not allowed"):
        await runtime.invoke(
            "get_asset_status",
            {"site_code": "HN-02"},
            authorization_context(frozenset({"HN-01"})),
        )

    assert handler.calls == [{"site_code": "HN-01"}]

    async with create_session_factory(engine)() as session:
        audit_records = list((await session.execute(select(AssistantToolAuditRecord))).scalars())
        trace_events = list((await session.execute(select(AssistantToolTraceEvent))).scalars())

    assert [record.decision for record in audit_records] == ["approved", "rejected"]
    assert [event.event for event in trace_events] == ["handler_executed", "permission_denied"]

    await engine.dispose()