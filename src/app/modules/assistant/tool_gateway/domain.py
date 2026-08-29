from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel

from app.modules.user.domain.authorization import Permission
from app.shared.kernel.response_evidence import EvidenceBlock


class ToolApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    APPROVAL_REQUIRED = "approval_required"
    RATE_LIMITED = "rate_limit"


class ToolExecutionStatus(StrEnum):
    SUCCESS = "success"
    REJECTED = "rejected"
    APPROVAL_REQUIRED = "approval_required"
    RATE_LIMITED = "rate_limited"
    FAILED = "failed"


class SideEffectType(StrEnum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True, slots=True)
class ToolRateLimit:
    max_calls: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.max_calls < 1:
            raise ValueError("max_calls must be at least 1")
        if self.window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
    required_permission: Permission
    site_code_field: str | None = None
    requires_approval: bool = False
    max_retries: int = 0
    approval_scope: str = "write"
    rate_limit: ToolRateLimit | None = None
    side_effect_type: SideEffectType = SideEffectType.READ


@dataclass(slots=True)
class ToolAuditRecord:
    tool_name: str
    actor: str | None
    payload: dict[str, Any]
    decision: ToolApprovalDecision
    conversation_id: UUID | None = None
    reason: str | None = None
    created_at_utc: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ToolTraceEvent:
    tool_name: str
    actor: str | None
    event: str
    payload: dict[str, Any]
    conversation_id: UUID | None = None
    created_at_utc: datetime = field(default_factory=lambda: datetime.now(UTC))


class ToolResultAdapter(Protocol):
    def to_evidence(
        self,
        *,
        applied_payload: Mapping[str, object],
        output: BaseModel,
    ) -> tuple[EvidenceBlock, ...]: ...


@dataclass(frozen=True, slots=True)
class AssistantToolRegistration:
    definition: ToolDefinition
    result_adapter: ToolResultAdapter
