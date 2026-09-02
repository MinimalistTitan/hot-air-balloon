from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database.database import Base, SessionFactory, create_session_factory
from app.modules.assistant.infrastructure.agents.langgraph.checkpoint_eraser import (
    LangGraphCheckpointEraser,
)
from app.modules.assistant.infrastructure.agents.langgraph.thread_identity import derive_thread_id
from app.modules.assistant.infrastructure.conversation_memory.models import (
    AssistantConversationRecord,
    ConversationTurnRecord,
)
from app.modules.assistant.infrastructure.conversation_memory.short_term.short_term_retention_job import (
    ShortTermRetentionJob,
)


class RecordingSaver(InMemorySaver):
    def __init__(self) -> None:
        super().__init__()
        self.deleted_thread_ids: list[str] = []

    async def adelete_thread(self, thread_id: str) -> None:
        self.deleted_thread_ids.append(thread_id)


class RecordingCheckpointEraser:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.calls: list[tuple[UUID, UUID]] = []
        self.failure = failure

    async def erase_conversation(
        self,
        owner_user_id: UUID,
        conversation_id: UUID,
    ) -> None:
        self.calls.append((owner_user_id, conversation_id))
        if self.failure is not None:
            raise self.failure


async def _seed_conversation(
    session_factory: SessionFactory,
    *,
    owner_user_id: UUID,
    conversation_id: UUID,
    turn_id: UUID,
    created_at: datetime,
    expires_at: datetime,
) -> None:
    async with session_factory() as session:
        session.add(
            AssistantConversationRecord(
                id=conversation_id,
                owner_user_id=owner_user_id,
                started_at=created_at,
                last_turn_at=created_at,
                turn_count=1,
                consolidated_at=None,
                closed_at=None,
            )
        )
        session.add(
            ConversationTurnRecord(
                id=turn_id,
                conversation_id=conversation_id,
                owner_user_id=owner_user_id,
                role="user",
                content="expired",
                created_at=created_at,
                expires_at=expires_at,
            )
        )
        await session.commit()


async def test_langgraph_checkpoint_eraser_uses_trusted_thread_derivation() -> None:
    saver = RecordingSaver()
    owner_user_id = uuid4()
    conversation_id = uuid4()
    eraser = LangGraphCheckpointEraser(checkpointer=saver)

    await eraser.erase_conversation(owner_user_id, conversation_id)

    assert saver.deleted_thread_ids == [
        derive_thread_id(
            owner_user_id=owner_user_id,
            conversation_id=conversation_id,
        ),
        str(conversation_id),
    ]


async def test_retention_erases_checkpoint_before_committing_expired_turn() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    owner_user_id = uuid4()
    conversation_id = uuid4()
    turn_id = uuid4()
    now = datetime.now(UTC)
    await _seed_conversation(
        session_factory,
        owner_user_id=owner_user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        created_at=now,
        expires_at=now - timedelta(seconds=1),
    )
    checkpoint_eraser = RecordingCheckpointEraser()
    job = ShortTermRetentionJob(
        session_factory=session_factory,
        checkpoint_eraser=checkpoint_eraser,
    )

    assert await job.purge_expired() == 1
    assert checkpoint_eraser.calls == [(owner_user_id, conversation_id)]

    async with session_factory() as session:
        assert (
            await session.scalar(
                select(ConversationTurnRecord.id).where(ConversationTurnRecord.id == turn_id)
            )
            is None
        )
    await engine.dispose()


async def test_checkpoint_failure_rolls_back_transcript_retention() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    owner_user_id = uuid4()
    conversation_id = uuid4()
    turn_id = uuid4()
    now = datetime.now(UTC)
    await _seed_conversation(
        session_factory,
        owner_user_id=owner_user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        created_at=now,
        expires_at=now - timedelta(seconds=1),
    )
    job = ShortTermRetentionJob(
        session_factory=session_factory,
        checkpoint_eraser=RecordingCheckpointEraser(
            failure=RuntimeError("checkpoint database unavailable")
        ),
    )

    with pytest.raises(RuntimeError, match="checkpoint database unavailable"):
        await job.purge_expired()

    async with session_factory() as session:
        assert (
            await session.scalar(
                select(ConversationTurnRecord.id).where(ConversationTurnRecord.id == turn_id)
            )
            == turn_id
        )
    await engine.dispose()


async def test_retention_erases_checkpoint_for_empty_stale_conversation() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    owner_user_id = uuid4()
    conversation_id = uuid4()
    stale_at = datetime.now(UTC) - timedelta(days=181)
    async with session_factory() as session:
        session.add(
            AssistantConversationRecord(
                id=conversation_id,
                owner_user_id=owner_user_id,
                started_at=stale_at,
                last_turn_at=stale_at,
                turn_count=0,
                consolidated_at=None,
                closed_at=None,
            )
        )
        await session.commit()

    checkpoint_eraser = RecordingCheckpointEraser()
    job = ShortTermRetentionJob(
        session_factory=session_factory,
        assistant_conversation_retention_days=180,
        checkpoint_eraser=checkpoint_eraser,
    )

    assert await job.purge_expired() == 0
    assert checkpoint_eraser.calls == [(owner_user_id, conversation_id)]
    async with session_factory() as session:
        assert (
            await session.scalar(
                select(AssistantConversationRecord.id).where(
                    AssistantConversationRecord.id == conversation_id
                )
            )
            is None
        )
    await engine.dispose()
