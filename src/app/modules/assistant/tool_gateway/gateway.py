from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.modules.assistant.tool_gateway.domain import (
    ToolApprovalDecision,
    ToolAuditRecord,
    ToolExecutionStatus,
    ToolTraceEvent,
)
from app.modules.assistant.tool_gateway.permissions import PermissionChecker
from app.modules.assistant.tool_gateway.policy import PolicyApprovalService
from app.modules.assistant.tool_gateway.rate_limit import RateLimiterPort
from app.modules.assistant.tool_gateway.registry import ToolRegistry, validate_strict_input
from app.modules.user.domain.authorization import AuthorizationContext


class ToolAuditSink(Protocol):
    async def write(self, record: ToolAuditRecord) -> None: ...


class ToolTraceSink(Protocol):
    async def append(self, event: ToolTraceEvent) -> None: ...


class ToolGateway:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        permission_checker: PermissionChecker,
        approval_service: PolicyApprovalService | None,
        audit_sink: ToolAuditSink,
        trace_sink: ToolTraceSink,
        rate_limiter: RateLimiterPort | None = None,
    ) -> None:
        self._registry = registry
        self._permission_checker = permission_checker
        self._approval_service = approval_service
        self._audit_sink = audit_sink
        self._trace_sink = trace_sink
        self._rate_limiter = rate_limiter

    async def invoke(
        self,
        *,
        tool_name: str,
        payload: dict[str, Any],
        authorization_context: AuthorizationContext,
        conversation_id: UUID | None = None,
    ) -> dict[str, Any]:
        tool = self._registry.get(tool_name)
        if tool is None:
            raise KeyError(f"unknown tool: {tool_name}")

        validated = validate_strict_input(tool.input_model, payload)
        validated_payload = validated.model_dump(mode="json")
        site_code: str | None = None
        if tool.site_code_field is not None:
            site_code_value = validated_payload.get(tool.site_code_field)
            if site_code_value is not None and not isinstance(site_code_value, str):
                raise TypeError(f"{tool.site_code_field} must be a string when present")
            site_code = site_code_value

        actor = str(authorization_context.user_id)
        allowed = await self._permission_checker.can_call(
            authorization_context,
            tool.required_permission,
            site_code=site_code,
        )
        if not allowed:
            await self._audit_sink.write(
                ToolAuditRecord(
                    tool_name=tool.name,
                    actor=actor,
                    payload=validated_payload,
                    decision=ToolApprovalDecision.REJECTED,
                    conversation_id=conversation_id,
                    reason=f"missing permission: {tool.required_permission.value}",
                )
            )
            await self._trace_sink.append(
                ToolTraceEvent(
                    tool_name=tool.name,
                    actor=actor,
                    conversation_id=conversation_id,
                    event="permission_denied",
                    payload={"required_permission": tool.required_permission.value},
                )
            )
            raise PermissionError(f"tool not allowed: {tool_name}")

        if tool.rate_limit is not None and self._rate_limiter is not None:
            verdict = self._rate_limiter.try_consume(
                actor=actor,
                tool_name=tool.name,
                rate_limit=tool.rate_limit,
            )
            if not verdict.allowed:
                await self._audit_sink.write(
                    ToolAuditRecord(
                        tool_name=tool.name,
                        actor=actor,
                        payload=validated_payload,
                        decision=ToolApprovalDecision.RATE_LIMITED,
                        conversation_id=conversation_id,
                        reason=(
                            f"rate limit exceeded: {tool.rate_limit.max_calls} calls "
                            f"per {tool.rate_limit.window_seconds}s"
                        ),
                    )
                )
                await self._trace_sink.append(
                    ToolTraceEvent(
                        tool_name=tool.name,
                        actor=actor,
                        conversation_id=conversation_id,
                        event="rate_limited",
                        payload={"retry_after_seconds": verdict.retry_after_seconds},
                    )
                )
                return {
                    "status": ToolExecutionStatus.RATE_LIMITED.value,
                    "tool_name": tool.name,
                    "retry_after_seconds": verdict.retry_after_seconds,
                }

        decision = ToolApprovalDecision.APPROVED
        reason: str | None = None

        if tool.requires_approval:
            if self._approval_service is None:
                decision = ToolApprovalDecision.APPROVAL_REQUIRED
                reason = "approval service not configured"
            else:
                decision = await self._approval_service.evaluate(
                    tool_name=tool.name,
                    actor=actor,
                    payload=validated_payload,
                )
                reason = None if decision == ToolApprovalDecision.APPROVED else "approval required"

        audit_record = ToolAuditRecord(
            tool_name=tool.name,
            actor=actor,
            payload=validated_payload,
            decision=decision,
            conversation_id=conversation_id,
            reason=reason,
        )
        await self._audit_sink.write(audit_record)

        if decision != ToolApprovalDecision.APPROVED:
            await self._trace_sink.append(
                ToolTraceEvent(
                    tool_name=tool.name,
                    actor=actor,
                    conversation_id=conversation_id,
                    event="approval_blocked",
                    payload={"decision": decision.value},
                )
            )
            return {
                "status": ToolExecutionStatus.APPROVAL_REQUIRED.value,
                "tool_name": tool.name,
                "decision": decision.value,
            }

        attempts = 0
        while True:
            try:
                raw_output = await tool.handler(validated_payload)
                result_model = tool.output_model.model_validate(raw_output)
                result = result_model.model_dump(mode="json")
                break
            except Exception:
                if attempts >= tool.max_retries:
                    raise
                attempts += 1

        await self._trace_sink.append(
            ToolTraceEvent(
                tool_name=tool.name,
                actor=actor,
                conversation_id=conversation_id,
                event="handler_executed",
                payload={"attempts": attempts + 1},
            )
        )

        return {
            "status": ToolExecutionStatus.SUCCESS.value,
            "tool_name": tool.name,
            "result": result,
        }
