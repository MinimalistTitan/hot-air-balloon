from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AssistantToolCallTraceV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    payload: dict[str, object]
    result: dict[str, object]


class AssistantQueryRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    conversation_id: UUID | None = None
    max_tool_calls: int = Field(default=4, ge=0, le=10)
    allow_tool_calls: bool = True


class AssistantQueryResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    conversation_id: UUID
    agent_name: str
    model_name: str
    finish_reason: str
    tool_calls: list[AssistantToolCallTraceV1] = []
    generated_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))