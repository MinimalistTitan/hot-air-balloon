from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select

from app.core.database.database import SessionFactory
from app.modules.assistant.application.ports import (
    EraseUserMemoryResult,
    UserMemoryErasePort,
    VectorIndexPort,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.models import (
    AssistantMemoryRecord,
)
from app.modules.assistant.infrastructure.conversation_memory.models import (
    AssistantConversationRecord,
    ConversationTurnRecord,
)


@dataclass(slots=True)
class UserMemoryEraser(UserMemoryErasePort):
    session_factory: SessionFactory
    vector_index: VectorIndexPort

    async def erase_user_memory(self, owner_user_id: UUID) -> EraseUserMemoryResult:
        async with self.session_factory() as session:
            user_turn_ids = set(
                (
                    await session.scalars(
                        select(ConversationTurnRecord.id).where(
                            ConversationTurnRecord.owner_user_id == owner_user_id
                        )
                    )
                ).all()
            )
            memory_rows = list(
                (
                    await session.scalars(
                        select(AssistantMemoryRecord).where(AssistantMemoryRecord.deleted_at.is_(None))
                    )
                ).all()
            )

        matched_rows = [
            row
            for row in memory_rows
            if row.owner_user_id == owner_user_id
            or any(turn_id in user_turn_ids for turn_id in row.source_turn_ids)
        ]
        vector_ids_by_namespace: defaultdict[str, list[str]] = defaultdict(list)
        for row in matched_rows:
            vector_ids_by_namespace[row.vector_namespace].append(row.vector_id)

        deleted_vectors = 0
        for namespace, vector_ids in vector_ids_by_namespace.items():
            await self.vector_index.delete_ids(namespace, vector_ids)
            deleted_vectors += len(vector_ids)

        memory_ids = [row.id for row in matched_rows]
        deleted_memory_records = 0
        deleted_turns = 0
        deleted_conversations = 0
        async with self.session_factory() as session:
            if memory_ids:
                await session.execute(
                    delete(AssistantMemoryRecord).where(AssistantMemoryRecord.id.in_(memory_ids))
                )
                deleted_memory_records = len(memory_ids)

            turn_ids = list(
                (
                    await session.scalars(
                        select(ConversationTurnRecord.id).where(
                            ConversationTurnRecord.owner_user_id == owner_user_id
                        )
                    )
                ).all()
            )
            if turn_ids:
                await session.execute(
                    delete(ConversationTurnRecord).where(ConversationTurnRecord.id.in_(turn_ids))
                )
            deleted_turns = len(turn_ids)

            conversation_ids = list(
                (
                    await session.scalars(
                        select(AssistantConversationRecord.id).where(
                            AssistantConversationRecord.owner_user_id == owner_user_id
                        )
                    )
                ).all()
            )
            if conversation_ids:
                await session.execute(
                    delete(AssistantConversationRecord).where(
                        AssistantConversationRecord.id.in_(conversation_ids)
                    )
                )
            deleted_conversations = len(conversation_ids)

            await session.commit()

        return EraseUserMemoryResult(
            deleted_memory_records=deleted_memory_records,
            deleted_vectors=deleted_vectors,
            deleted_turns=deleted_turns,
            deleted_conversations=deleted_conversations,
        )
