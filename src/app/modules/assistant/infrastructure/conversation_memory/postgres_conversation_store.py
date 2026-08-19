from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import delete, select

from app.core.database.database import SessionFactory
from app.modules.assistant.application.ports import ConversationStorePort, ConversationTurn
from app.modules.assistant.infrastructure.conversation_memory.models import ConversationTurnRecord


@dataclass(slots=True)
class PostgresConversationStore(ConversationStorePort):
    session_factory: SessionFactory
    max_turns_per_conversation: int = 50

    async def read_recent(
        self,
        conversation_id: UUID,
        limit: int = 12,
    ) -> list[ConversationTurn]:
        if limit <= 0:
            return []

        statement = (
            select(ConversationTurnRecord)
            .where(ConversationTurnRecord.conversation_id == conversation_id)
            .order_by(ConversationTurnRecord.created_at.desc(), ConversationTurnRecord.id.desc())
            .limit(limit)
        )
        async with self.session_factory() as session:
            records = list((await session.scalars(statement)).all())

        records.reverse()
        return [
            ConversationTurn(
                role=record.role,
                content=record.content,
                created_at_utc=record.created_at,
            )
            for record in records
        ]

    async def append(self, conversation_id: UUID, turn: ConversationTurn) -> None:
        async with self.session_factory() as session:
            session.add(
                ConversationTurnRecord(
                    id=uuid4(),
                    conversation_id=conversation_id,
                    role=turn.role,
                    content=turn.content,
                    created_at=turn.created_at_utc,
                )
            )
            await session.flush()

            excess_turn_ids = (
                select(ConversationTurnRecord.id)
                .where(ConversationTurnRecord.conversation_id == conversation_id)
                .order_by(ConversationTurnRecord.created_at.desc(), ConversationTurnRecord.id.desc())
                .offset(self.max_turns_per_conversation)
            )
            await session.execute(
                delete(ConversationTurnRecord).where(
                    ConversationTurnRecord.id.in_(excess_turn_ids)
                )
            )
            await session.commit()