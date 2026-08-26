from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.core.database.database import SessionFactory
from app.modules.assistant.application.ports import ToolRuntimePort
from app.modules.assistant.domain.entities import ToolDescriptor
from app.modules.assistant.tool_gateway.rate_limit import (
    FixedWindowRateLimiter,
    RateLimiterPort,
)
from app.modules.assistant.tool_gateway.registry import ToolRegistry
from app.modules.assistant.tool_gateway.wiring import build_tool_gateway
from app.modules.user.domain.authorization import AuthorizationContext


@dataclass(slots=True)
class GatewayToolRuntime(ToolRuntimePort):
    registry: ToolRegistry
    session_factory: SessionFactory
    allow_write_tools: bool = False
    rate_limiter: RateLimiterPort | None = None

    def __post_init__(self) -> None:
        if self.rate_limiter is None:
            self.rate_limiter = FixedWindowRateLimiter()

    async def list_tools(
        self,
        authorization_context: AuthorizationContext,
    ) -> list[ToolDescriptor]:
        return [
            ToolDescriptor(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_model.model_json_schema(),
                site_code_field=tool.site_code_field,
                is_mutating=tool.side_effect_type.value == "write",
            )
            for tool in self.registry.list_tools()
            if authorization_context.can(tool.required_permission)
            and (
                tool.site_code_field is None
                or authorization_context.global_scope
                or bool(authorization_context.site_codes)
            )
        ]

    async def invoke(
        self,
        tool_name: str,
        payload: dict[str, object],
        authorization_context: AuthorizationContext,
        conversation_id: UUID | None = None,
    ) -> dict[str, object]:
        async with self.session_factory() as session:
            gateway = build_tool_gateway(
                registry=self.registry,
                session=session,
                allow_write_tools=self.allow_write_tools,
                rate_limiter=self.rate_limiter,
            )
            try:
                result = await gateway.invoke(
                    tool_name=tool_name,
                    payload=payload,
                    authorization_context=authorization_context,
                    conversation_id=conversation_id,
                )
                await session.commit()
            except Exception:
                await session.commit()
                raise

        return result
