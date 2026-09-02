from typing import Annotated, Literal, NotRequired, TypedDict

from app.modules.assistant.application.ports import ConversationTurn
from app.modules.assistant.domain.entities import ToolCallRecord, ToolDescriptor
from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from langgraph.channels import UntrackedValue

CURRENT_WORKFLOW_VERSION = 1


class PlannedAction(TypedDict):
    action: Literal["respond", "tool_call"]
    tool_name: str
    payload: dict[str, object]
    intent: NotRequired[str]
    confidence: NotRequired[float]
    rationale: NotRequired[str]


class PendingClarification(TypedDict):
    prompt: str


class PendingApproval(TypedDict):
    request_id: str
    prompt: str
    tool_name: str
    payload: dict[str, object]


class GraphState(TypedDict):
    """LangGraph channels; only non-UntrackedValue fields are checkpointed."""

    workflow_version: int
    pending_clarification: NotRequired[PendingClarification | None]
    pending_approval: NotRequired[PendingApproval | None]

    intent: Annotated[str, UntrackedValue]
    planned_action: Annotated[PlannedAction, UntrackedValue]
    pending_call: Annotated[ToolCallRecord | None, UntrackedValue]
    tool_calls: Annotated[list[ToolCallRecord], UntrackedValue]
    next_step: Annotated[Literal["continue", "respond"], UntrackedValue]
    answer: Annotated[str, UntrackedValue]
    finish_reason: Annotated[OrchestrationFinishReason | None, UntrackedValue]


class AgentStateView(TypedDict):
    """A request-scoped view supplied to the reasoning implementation."""

    user_query: str
    context_prompt: str
    available_tools: list[ToolDescriptor]
    conversation_history: list[ConversationTurn]
    intent: str
    planned_action: PlannedAction
    pending_call: ToolCallRecord | None
    tool_calls: list[ToolCallRecord]
    total_tool_calls: int
    per_tool_calls: dict[str, int]
    remaining_tool_calls: int
    max_calls_per_tool: int
    next_step: Literal["continue", "respond"]
    answer: str
    finish_reason: OrchestrationFinishReason | None
