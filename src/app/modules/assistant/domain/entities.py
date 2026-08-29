from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from app.shared.kernel.response_evidence import EvidenceBlock


class ToolOutcomeStatus(StrEnum):
    SUCCESS = "success"
    APPROVAL_REQUIRED = "approval_required"
    RATE_LIMITED = "rate_limited"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    name: str
    description: str
    input_hint: str | None = None
    input_schema: dict[str, object] = field(default_factory=dict)
    site_code_field: str | None = None
    is_mutating: bool = False


@dataclass(frozen=True, slots=True)
class ToolCallRecord:
    tool_name: str
    payload: dict[str, object]
    status: ToolOutcomeStatus
    evidence: tuple[EvidenceBlock, ...]
    # Temporary V1 compatibility. Never pass this field to an LLM.
    result: dict[str, object] = field(repr=False)


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    answer: str
    agent_name: str
    model_name: str
    finish_reason: OrchestrationFinishReason
    tool_calls: list[ToolCallRecord]
    evidence: tuple[EvidenceBlock, ...]


class DecisionStage(StrEnum):
    PLANNING = "planning"
    PRE_EXECUTION = "pre_execution"
    RESULT_VALIDATION = "result_validation"


class DecisionOutcome(StrEnum):
    SELECTED = "selected"
    ALLOWED = "allowed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class AssistantDecisionEvent:
    conversation_id: UUID | None
    stage: DecisionStage
    outcome: DecisionOutcome
    source: str
    intent: str | None = None
    confidence: float | None = None
    action: str | None = None
    tool_name: str | None = None
    reason_code: str | None = None
    callable_tool_count: int | None = None
