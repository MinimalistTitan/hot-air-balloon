from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class AssistantQueryHandledV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    occurred_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    conversation_id: UUID | None = None
    user_query: str
    answer_preview: str
    tools_used: list[str] = []