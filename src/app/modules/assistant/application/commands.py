from dataclasses import dataclass
from uuid import UUID

from app.modules.user.domain.authorization import AuthorizationContext


@dataclass(frozen=True, slots=True)
class AssistantQueryCommand:
    query: str
    authorization_context: AuthorizationContext
    conversation_id: UUID | None = None
    max_tool_calls: int = 4
    allow_tool_calls: bool = True