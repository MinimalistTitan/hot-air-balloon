from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID

from app.modules.assistant.application.ports import (
    ConversationStorePort,
    ConversationTurn,
    MemoryWriterPort,
)


@dataclass(slots=True)
class InMemoryConversationStore(ConversationStorePort, MemoryWriterPort):
    max_turns_per_conversation: int = 5
    _state: dict[UUID, list[ConversationTurn]] = field(default_factory=lambda: defaultdict(list))

    async def read_recent(self, conversation_id: UUID, limit: int = 3, owner_user_id: UUID | None = None) -> list[ConversationTurn]:
        turns = self._state.get(conversation_id, [])
        if limit <= 0:
            return []
        return turns[-limit:]

    async def append(self, conversation_id: UUID, turn: ConversationTurn, owner_user_id: UUID | None = None) -> None:
        turns = self._state[conversation_id]
        turns.append(turn)
        if len(turns) > self.max_turns_per_conversation:
            overflow = len(turns) - self.max_turns_per_conversation
            del turns[:overflow]

    async def record_turn(
        self,
        conversation_id: UUID,
        turn: ConversationTurn,
        owner_user_id: UUID | None = None,
    ) -> None:
        await self.append(conversation_id, turn, owner_user_id=owner_user_id)

    async def close_conversation(
        self,
        conversation_id: UUID,
        owner_user_id: UUID | None = None,
    ) -> None:
        del owner_user_id
        self._state.setdefault(conversation_id, [])
