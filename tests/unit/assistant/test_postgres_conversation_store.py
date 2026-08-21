from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database.database import Base, create_session_factory
from app.modules.assistant.application.ports import ConversationTurn
from app.modules.assistant.infrastructure.conversation_memory.models import ConversationTurnRecord
from app.modules.assistant.infrastructure.conversation_memory.short_term.postgres_conversation_store import (
    ConversationStore,
)


async def test_store_returns_recent_turns_in_chronological_order() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    store = ConversationStore(
        session_factory=create_session_factory(engine),
        max_turns_per_conversation=2,
    )
    conversation_id = uuid4()
    created_at = datetime.now(UTC)
    for offset, content in enumerate(["first", "second", "third"]):
        await store.append(
            conversation_id,
            ConversationTurn(
                role="user",
                content=content,
                created_at_utc=created_at + timedelta(seconds=offset),
            ),
        )

    turns = await store.read_recent(conversation_id)

    assert [turn.content for turn in turns] == ["first", "second", "third"]
    await engine.dispose()


async def test_store_stamps_expiration_and_filters_by_owner() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    store = ConversationStore(session_factory=create_session_factory(engine))
    conversation_id = uuid4()
    owner_user_id = uuid4()
    created_at = datetime.now(UTC)

    await store.append(
        conversation_id,
        ConversationTurn(
            role="user",
            content="hello",
            created_at_utc=created_at,
        ),
        owner_user_id=owner_user_id,
    )

    assert await store.read_recent(conversation_id, owner_user_id=owner_user_id) == [
        ConversationTurn(
            role="user",
            content="hello",
            created_at_utc=created_at,
        )
    ]
    assert await store.read_recent(conversation_id, owner_user_id=uuid4()) == []

    async with engine.begin() as connection:
        result = await connection.execute(
            select(ConversationTurnRecord.id, ConversationTurnRecord.expires_at).where(
                ConversationTurnRecord.conversation_id == conversation_id
            )
        )
        record_id, expires_at = result.one()
        assert record_id is not None
        assert expires_at == created_at + timedelta(days=90)

    await engine.dispose()
