from typing import Literal, NotRequired, TypedDict

from app.modules.assistant.application.ports import ConversationTurn
from app.modules.assistant.domain.entities import ToolCallRecord, ToolDescriptor
from app.modules.assistant.domain.value_object import OrchestrationFinishReason


class PlannedAction(TypedDict):
    action: Literal["respond", "tool_call"]
    tool_name: str
    payload: dict[str, object]
    intent: NotRequired[str]
    confidence: NotRequired[float]
    rationale: NotRequired[str]


class GraphState(TypedDict):
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
