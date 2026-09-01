from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import case, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import SessionFactory
from app.modules.assistant.application.ports import (
    ConversationStorePort,
    ConversationTurn,
    MemoryWriterPort,
)
from app.modules.assistant.domain.errors import ConversationOwnershipError
from app.modules.assistant.infrastructure.conversation_memory.models import (
    AssistantConversationRecord,
    ConversationTurnRecord,
)


@dataclass(slots=True)
class ConversationStore(ConversationStorePort, MemoryWriterPort):
    session_factory: SessionFactory
    max_turns_per_conversation: int = 50
    retention_days: int = 90

    async def claim_or_validate(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
        observed_at_utc: datetime,
    ) -> None:
        async with self.session_factory() as session, session.begin():
            await self._claim_or_validate(
                session,
                conversation_id=conversation_id,
                owner_user_id=owner_user_id,
                observed_at_utc=observed_at_utc,
            )

    async def read_recent(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
        limit: int = 12,
    ) -> list[ConversationTurn]:
        async with self.session_factory() as session:
            await self._require_owner(
                session,
                conversation_id=conversation_id,
                owner_user_id=owner_user_id,
            )
            if limit <= 0:
                return []

            statement = (
                select(ConversationTurnRecord)
                .where(
                    ConversationTurnRecord.conversation_id == conversation_id,
                    ConversationTurnRecord.owner_user_id == owner_user_id,
                )
                .order_by(
                    ConversationTurnRecord.created_at.desc(),
                    ConversationTurnRecord.id.desc(),
                )
                .limit(limit)
            )
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
        owner_user_id: UUID,
    ) -> None:
        async with self.session_factory() as session, session.begin():
            await self._claim_or_validate(
                session,
                conversation_id=conversation_id,
                owner_user_id=owner_user_id,
                observed_at_utc=turn.created_at_utc,
            )
            session.add(self._turn_record(conversation_id, owner_user_id, turn))
            await self._advance_conversation(
                session,
                conversation_id=conversation_id,
                owner_user_id=owner_user_id,
                touched_at=turn.created_at_utc,
                turn_count_increment=1,
            )

    async def append_completed_exchange(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
        user_turn: ConversationTurn,
        assistant_turn: ConversationTurn,
    ) -> None:
        if user_turn.role != "user" or assistant_turn.role != "assistant":
            raise ValueError("A completed exchange requires one user and one assistant turn")

        async with self.session_factory() as session, session.begin():
            await self._claim_or_validate(
                session,
                conversation_id=conversation_id,
                owner_user_id=owner_user_id,
                observed_at_utc=user_turn.created_at_utc,
            )
            session.add_all(
                (
                    self._turn_record(conversation_id, owner_user_id, user_turn),
                    self._turn_record(conversation_id, owner_user_id, assistant_turn),
                )
            )
            await self._advance_conversation(
                session,
                conversation_id=conversation_id,
                owner_user_id=owner_user_id,
                touched_at=assistant_turn.created_at_utc,
                turn_count_increment=2,
            )

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
        async with self.session_factory() as session, session.begin():
            await self._require_owner(
                session,
                conversation_id=conversation_id,
                owner_user_id=owner_user_id,
            )
            statement = select(ConversationTurnRecord).where(
                ConversationTurnRecord.conversation_id == conversation_id,
                ConversationTurnRecord.owner_user_id == owner_user_id,
            )
            rows = list((await session.scalars(statement)).all())
            for row in rows:
                row.expires_at = row.created_at + timedelta(days=self.retention_days)

            close_statement = (
                update(AssistantConversationRecord)
                .where(
                    AssistantConversationRecord.id == conversation_id,
                    AssistantConversationRecord.owner_user_id == owner_user_id,
                )
                .values(closed_at=datetime.now(UTC))
                .returning(AssistantConversationRecord.id)
            )
            if (await session.execute(close_statement)).scalar_one_or_none() is None:
                raise ConversationOwnershipError

    async def _claim_or_validate(
        self,
        session: AsyncSession,
        *,
        conversation_id: UUID,
        owner_user_id: UUID,
        observed_at_utc: datetime,
    ) -> None:
        values = {
            "id": conversation_id,
            "owner_user_id": owner_user_id,
            "started_at": observed_at_utc,
            "last_turn_at": observed_at_utc,
            "turn_count": 0,
            "consolidated_at": None,
            "closed_at": None,
        }
        dialect_name = session.get_bind().dialect.name
        insert_statement: Any
        if dialect_name == "postgresql":
            insert_statement = postgresql_insert(AssistantConversationRecord).values(**values)
        elif dialect_name == "sqlite":
            insert_statement = sqlite_insert(AssistantConversationRecord).values(**values)
        else:
            raise RuntimeError(f"Unsupported conversation-store dialect: {dialect_name}")

        claim_statement = insert_statement.on_conflict_do_update(
            index_elements=[AssistantConversationRecord.id],
            set_={"last_turn_at": AssistantConversationRecord.last_turn_at},
            where=AssistantConversationRecord.owner_user_id
            == insert_statement.excluded.owner_user_id,
        ).returning(AssistantConversationRecord.id)
        claimed_id = (await session.execute(claim_statement)).scalar_one_or_none()
        if claimed_id is None:
            raise ConversationOwnershipError

    async def _require_owner(
        self,
        session: AsyncSession,
        *,
        conversation_id: UUID,
        owner_user_id: UUID,
    ) -> None:
        statement = select(AssistantConversationRecord.id).where(
            AssistantConversationRecord.id == conversation_id,
            AssistantConversationRecord.owner_user_id == owner_user_id,
        )
        if (await session.scalar(statement)) is None:
            raise ConversationOwnershipError

    async def _advance_conversation(
        self,
        session: AsyncSession,
        *,
        conversation_id: UUID,
        owner_user_id: UUID,
        touched_at: datetime,
        turn_count_increment: int,
    ) -> None:
        statement = (
            update(AssistantConversationRecord)
            .where(
                AssistantConversationRecord.id == conversation_id,
                AssistantConversationRecord.owner_user_id == owner_user_id,
            )
            .values(
                last_turn_at=case(
                    (AssistantConversationRecord.last_turn_at < touched_at, touched_at),
                    else_=AssistantConversationRecord.last_turn_at,
                ),
                turn_count=AssistantConversationRecord.turn_count + turn_count_increment,
                closed_at=None,
            )
            .returning(AssistantConversationRecord.id)
        )
        if (await session.execute(statement)).scalar_one_or_none() is None:
            raise ConversationOwnershipError

    def _turn_record(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
        turn: ConversationTurn,
    ) -> ConversationTurnRecord:
        return ConversationTurnRecord(
            id=uuid4(),
            conversation_id=conversation_id,
            owner_user_id=owner_user_id,
            role=turn.role,
            content=turn.content,
            created_at=turn.created_at_utc,
            expires_at=turn.created_at_utc + timedelta(days=self.retention_days),
        )
