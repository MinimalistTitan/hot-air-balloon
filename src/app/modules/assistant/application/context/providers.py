from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from app.modules.assistant.application.ports import ConversationTurn
from app.modules.assistant.domain.context import ContextBlock
from app.modules.assistant.domain.conversation_evidence import ConversationEvidenceSnapshot
from app.modules.user.domain.authorization import AuthorizationContext


@dataclass(frozen=True, slots=True)
class ContextRequest:
    conversation_id: UUID
    user_query: str
    authorization_context: AuthorizationContext
    recent_turns: list[ConversationTurn] = field(default_factory=list)
    recent_evidence: list[ConversationEvidenceSnapshot] = field(default_factory=list)


class ContextProviderPort(Protocol):
    async def get_blocks(self, request: ContextRequest) -> list[ContextBlock]: ...
