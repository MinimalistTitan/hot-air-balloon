from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID

from app.modules.assistant.application.ports import ConversationStorePort, ConversationTurn


@dataclass(slots=True)
class InMemoryConversationStore(ConversationStorePort):
    max_turns_per_conversation: int = 50
    _state: dict[UUID, list[ConversationTurn]] = field(default_factory=lambda: defaultdict(list))

    async def read_recent(self, conversation_id: UUID, limit: int = 12) -> list[ConversationTurn]:
        turns = self._state.get(conversation_id, [])
        if limit <= 0:
            return []
        return turns[-limit:]

    async def append(self, conversation_id: UUID, turn: ConversationTurn) -> None:
        turns = self._state[conversation_id]
        turns.append(turn)
        if len(turns) > self.max_turns_per_conversation:
            overflow = len(turns) - self.max_turns_per_conversation
            del turns[:overflow]