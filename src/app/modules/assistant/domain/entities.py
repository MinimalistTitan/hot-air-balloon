from dataclasses import dataclass, field

from app.modules.assistant.domain.value_object import OrchestrationFinishReason


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    name: str
    description: str
    input_hint: str | None = None
    input_schema: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolCallRecord:
    tool_name: str
    payload: dict[str, object]
    result: dict[str, object]


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    answer: str
    agent_name: str
    model_name: str
    finish_reason: OrchestrationFinishReason
    tool_calls: list[ToolCallRecord]
