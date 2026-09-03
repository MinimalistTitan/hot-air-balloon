from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import AnyMessage

from app.modules.assistant.domain.entities import ToolCallRecord, ToolDescriptor
from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from langgraph.channels import UntrackedValue
from langgraph.graph.message import add_messages

CURRENT_WORKFLOW_VERSION = 3
MAX_WORKING_SET_ENTITIES = 32
WORKING_SET_ENTITY_FIELDS = frozenset(
    {
        "asset_code",
        "asset_id",
        "part_code",
        "part_id",
        "site_code",
        "ticket_id",
        "work_order_code",
        "work_order_id",
    }
)


class PlannedAction(TypedDict):
    action: Literal["respond", "tool_call"]
    tool_name: str
    payload: dict[str, object]
    answer: NotRequired[str]
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


class WorkingSetEntity(TypedDict):
    kind: str
    identifier: str


class ConversationWorkingSet(TypedDict):
    active_intent: str | None
    referenced_entities: list[WorkingSetEntity]


class ConversationMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


def merge_working_sets(
    current: ConversationWorkingSet,
    update: ConversationWorkingSet,
) -> ConversationWorkingSet:
    entities_by_key = {
        (entity["kind"], entity["identifier"]): entity
        for entity in [
            *current.get("referenced_entities", []),
            *update.get("referenced_entities", []),
        ]
    }
    return {
        "active_intent": update.get("active_intent") or current.get("active_intent"),
        "referenced_entities": list(entities_by_key.values())[-MAX_WORKING_SET_ENTITIES:],
    }


def working_set_entities(payload: dict[str, object]) -> list[WorkingSetEntity]:
    return [
        {"kind": field_name, "identifier": value}
        for field_name, value in payload.items()
        if field_name in WORKING_SET_ENTITY_FIELDS
        and isinstance(value, str)
        and 0 < len(value) <= 128
    ]


class GraphState(TypedDict):
    """LangGraph channels; only non-UntrackedValue fields are checkpointed."""

    workflow_version: int
    messages: Annotated[list[AnyMessage], add_messages]
    working_set: Annotated[ConversationWorkingSet, merge_working_sets]
    pending_clarification: NotRequired[PendingClarification | None]
    pending_approval: NotRequired[PendingApproval | None]

    intent: Annotated[str, UntrackedValue]
    planned_action: Annotated[PlannedAction, UntrackedValue]
    pending_call: Annotated[ToolCallRecord | None, UntrackedValue]
    tool_calls: Annotated[list[ToolCallRecord], UntrackedValue]
    answer: Annotated[str, UntrackedValue]
    finish_reason: Annotated[OrchestrationFinishReason | None, UntrackedValue]


class AgentStateView(TypedDict):
    """A request-scoped view supplied to the reasoning implementation."""

    user_query: str
    context_prompt: str
    available_tools: list[ToolDescriptor]
    conversation_history: list[ConversationMessage]
    intent: str
    planned_action: PlannedAction
    pending_call: ToolCallRecord | None
    tool_calls: list[ToolCallRecord]
    total_tool_calls: int
    per_tool_calls: dict[str, int]
    remaining_tool_calls: int
    max_calls_per_tool: int
    answer: str
    finish_reason: OrchestrationFinishReason | None
