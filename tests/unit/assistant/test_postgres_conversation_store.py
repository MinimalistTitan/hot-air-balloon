from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database.database import Base, create_session_factory
from app.modules.assistant.application.ports import ConversationTurn
from app.modules.assistant.infrastructure.conversation_memory.postgres_conversation_store import (
    PostgresConversationStore,
)


async def test_store_returns_recent_turns_in_chronological_order() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    store = PostgresConversationStore(
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

    assert [turn.content for turn in turns] == ["second", "third"]
    await engine.dispose()