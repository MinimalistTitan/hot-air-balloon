import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.modules.assistant.application.ports import (
    ConversationEvidenceStorePort,
    ConversationStorePort,
    ConversationTurn,
    MemoryWriterPort,
)
from app.modules.assistant.domain.conversation_evidence import ConversationEvidenceSnapshot
from app.modules.assistant.domain.errors import ConversationOwnershipError


@dataclass(slots=True)
class InMemoryConversationStore(
    ConversationStorePort,
    ConversationEvidenceStorePort,
    MemoryWriterPort,
):
    max_turns_per_conversation: int = 5
    _state: dict[UUID, list[ConversationTurn]] = field(default_factory=lambda: defaultdict(list))
    _evidence: dict[UUID, list[ConversationEvidenceSnapshot]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _owners: dict[UUID, UUID] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def claim_or_validate(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
        observed_at_utc: datetime,
    ) -> None:
        del observed_at_utc
        async with self._lock:
            self._claim_or_validate(conversation_id, owner_user_id)

    async def read_recent(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
        limit: int = 3,
    ) -> list[ConversationTurn]:
        async with self._lock:
            self._require_owner(conversation_id, owner_user_id)
            if limit <= 0:
                return []
            return list(self._state[conversation_id][-limit:])

    async def append(
        self,
        conversation_id: UUID,
        turn: ConversationTurn,
        owner_user_id: UUID,
    ) -> None:
        async with self._lock:
            self._claim_or_validate(conversation_id, owner_user_id)
            self._state[conversation_id].append(turn)
            self._trim(conversation_id)

    async def append_completed_exchange(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
        user_turn: ConversationTurn,
        assistant_turn: ConversationTurn,
        evidence: ConversationEvidenceSnapshot | None = None,
    ) -> None:
        if user_turn.role != "user" or assistant_turn.role != "assistant":
            raise ValueError("A completed exchange requires one user and one assistant turn")

        async with self._lock:
            self._claim_or_validate(conversation_id, owner_user_id)
            self._state[conversation_id].extend((user_turn, assistant_turn))
            self._trim(conversation_id)
            if evidence is not None:
                self._evidence[conversation_id].append(evidence)

    async def read_recent_evidence(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
        limit: int = 12,
    ) -> list[ConversationEvidenceSnapshot]:
        async with self._lock:
            self._require_owner(conversation_id, owner_user_id)
            if limit <= 0:
                return []
            return list(self._evidence[conversation_id][-limit:])

    async def append_evidence(self, snapshot: ConversationEvidenceSnapshot) -> None:
        async with self._lock:
            self._require_owner(snapshot.conversation_id, snapshot.owner_user_id)
            self._evidence[snapshot.conversation_id].append(snapshot)

    async def erase_evidence(self, conversation_id: UUID, owner_user_id: UUID) -> int:
        async with self._lock:
            self._require_owner(conversation_id, owner_user_id)
            deleted = len(self._evidence[conversation_id])
            self._evidence[conversation_id].clear()
            return deleted

    async def record_turn(
        self,
        conversation_id: UUID,
        turn: ConversationTurn,
        owner_user_id: UUID,
    ) -> None:
        await self.append(conversation_id, turn, owner_user_id=owner_user_id)

    async def close_conversation(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
    ) -> None:
        async with self._lock:
            self._require_owner(conversation_id, owner_user_id)

    def _claim_or_validate(self, conversation_id: UUID, owner_user_id: UUID) -> None:
        existing_owner = self._owners.get(conversation_id)
        if existing_owner is None:
            self._owners[conversation_id] = owner_user_id
            self._state.setdefault(conversation_id, [])
            return
        if existing_owner != owner_user_id:
            raise ConversationOwnershipError

    def _require_owner(self, conversation_id: UUID, owner_user_id: UUID) -> None:
        if self._owners.get(conversation_id) != owner_user_id:
            raise ConversationOwnershipError

    def _trim(self, conversation_id: UUID) -> None:
        turns = self._state[conversation_id]
        if len(turns) <= self.max_turns_per_conversation:
            return
        overflow = len(turns) - self.max_turns_per_conversation
        del turns[:overflow]
