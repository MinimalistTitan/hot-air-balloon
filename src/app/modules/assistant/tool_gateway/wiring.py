from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.assistant.infrastructure.tool_gateway.audit_repository import ToolAuditRepository
from app.modules.assistant.infrastructure.tool_gateway.trace_repository import ToolTraceRepository
from app.modules.assistant.tool_gateway.gateway import ToolGateway
from app.modules.assistant.tool_gateway.permissions import DefaultPermissionChecker
from app.modules.assistant.tool_gateway.policy import PolicyApprovalService
from app.modules.assistant.tool_gateway.rate_limit import FixedWindowRateLimiter, RateLimiterPort
from app.modules.assistant.tool_gateway.registry import ToolRegistry


def build_tool_gateway(
    *,
    registry: ToolRegistry,
    session: AsyncSession,
    allow_write_tools: bool = False,
    rate_limiter: RateLimiterPort | None = None,
) -> ToolGateway:
    permission_checker = DefaultPermissionChecker()
    audit_repository = ToolAuditRepository(session)
    trace_repository = ToolTraceRepository(session)

    return ToolGateway(
        registry=registry,
        permission_checker=permission_checker,
        approval_service=PolicyApprovalService(allow_write_tools=allow_write_tools),
        audit_sink=audit_repository,
        trace_sink=trace_repository,
        rate_limiter=rate_limiter if rate_limiter is not None else FixedWindowRateLimiter(),
    )