from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import SessionFactory
from app.modules.assistant.application.ports import (
    ConversationStorePort,
    ConversationTurn,
    MemoryWriterPort,
)
from app.modules.assistant.infrastructure.conversation_memory.models import (
    AssistantConversationRecord,
    ConversationTurnRecord,
)


@dataclass(slots=True)
class ConversationStore(ConversationStorePort, MemoryWriterPort):
    session_factory: SessionFactory
    max_turns_per_conversation: int = 50
    retention_days: int = 90

    async def read_recent(
        self,
        conversation_id: UUID,
        limit: int = 12,
        owner_user_id: UUID | None = None,
    ) -> list[ConversationTurn]:
        if limit <= 0:
            return []

        statement = (
            select(ConversationTurnRecord)
            .where(ConversationTurnRecord.conversation_id == conversation_id)
        )
        if owner_user_id is not None:
            statement = statement.where(ConversationTurnRecord.owner_user_id == owner_user_id)

        statement = (
            statement.order_by(ConversationTurnRecord.created_at.desc(), ConversationTurnRecord.id.desc())
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

    async def append(
        self,
        conversation_id: UUID,
        turn: ConversationTurn,
        owner_user_id: UUID | None = None,
    ) -> None:
        expires_at = turn.created_at_utc + timedelta(days=self.retention_days)
        async with self.session_factory() as session:
            session.add(
                ConversationTurnRecord(
                    id=uuid4(),
                    conversation_id=conversation_id,
                    owner_user_id=owner_user_id,
                    role=turn.role,
                    content=turn.content,
                    created_at=turn.created_at_utc,
                    expires_at=expires_at,
                )
            )
            await self._touch_conversation(
                session,
                conversation_id=conversation_id,
                owner_user_id=owner_user_id,
                touched_at=turn.created_at_utc,
            )
            await session.commit()

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
        async with self.session_factory() as session:
            statement = select(ConversationTurnRecord).where(ConversationTurnRecord.conversation_id == conversation_id)
            if owner_user_id is not None:
                statement = statement.where(ConversationTurnRecord.owner_user_id == owner_user_id)
            rows = list((await session.scalars(statement)).all())
            for row in rows:
                row.expires_at = row.created_at + timedelta(days=self.retention_days)
            await self._mark_closed(
                session,
                conversation_id=conversation_id,
                owner_user_id=owner_user_id,
            )
            await session.commit()

    async def _touch_conversation(
        self,
        session: AsyncSession,
        *,
        conversation_id: UUID,
        owner_user_id: UUID | None,
        touched_at: datetime,
    ) -> None:
        record = await session.get(AssistantConversationRecord, conversation_id)
        if record is None:
            session.add(
                AssistantConversationRecord(
                    id=conversation_id,
                    owner_user_id=owner_user_id,
                    started_at=touched_at,
                    last_turn_at=touched_at,
                    turn_count=1,
                    consolidated_at=None,
                    closed_at=None,
                )
            )
            return

        record.owner_user_id = owner_user_id
        record.last_turn_at = touched_at
        record.turn_count += 1
        record.closed_at = None

    async def _mark_closed(
        self,
        session: AsyncSession,
        *,
        conversation_id: UUID,
        owner_user_id: UUID | None,
    ) -> None:
        record = await session.get(AssistantConversationRecord, conversation_id)
        now = datetime.now(UTC)
        if record is None:
            session.add(
                AssistantConversationRecord(
                    id=conversation_id,
                    owner_user_id=owner_user_id,
                    started_at=now,
                    last_turn_at=now,
                    turn_count=0,
                    consolidated_at=None,
                    closed_at=now,
                )
            )
            return

        record.owner_user_id = owner_user_id
        record.closed_at = now
