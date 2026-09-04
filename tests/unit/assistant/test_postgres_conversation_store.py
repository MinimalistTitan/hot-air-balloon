from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database.database import Base, create_session_factory
from app.modules.assistant.application.ports import ConversationTurn
from app.modules.assistant.domain.conversation_evidence import ConversationEvidenceSnapshot
from app.modules.assistant.domain.errors import ConversationOwnershipError
from app.modules.assistant.infrastructure.conversation_memory.models import (
    AssistantConversationRecord,
    ConversationEvidenceRecord,
    ConversationTurnRecord,
)
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
    owner_user_id = uuid4()
    created_at = datetime.now(UTC)
    for offset, content in enumerate(["first", "second", "third"]):
        await store.append(
            conversation_id,
            ConversationTurn(
                role="user",
                content=content,
                created_at_utc=created_at + timedelta(seconds=offset),
            ),
            owner_user_id=owner_user_id,
        )

    turns = await store.read_recent(conversation_id, owner_user_id=owner_user_id)

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
    with pytest.raises(ConversationOwnershipError):
        await store.read_recent(conversation_id, owner_user_id=uuid4())

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


async def test_store_claim_keeps_owner_immutable() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    store = ConversationStore(session_factory=create_session_factory(engine))
    conversation_id = uuid4()
    owner_user_id = uuid4()
    other_user_id = uuid4()
    observed_at = datetime.now(UTC)

    await store.claim_or_validate(conversation_id, owner_user_id, observed_at)
    await store.claim_or_validate(conversation_id, owner_user_id, observed_at)
    with pytest.raises(ConversationOwnershipError):
        await store.claim_or_validate(conversation_id, other_user_id, observed_at)

    async with engine.begin() as connection:
        owner = await connection.scalar(
            select(AssistantConversationRecord.owner_user_id).where(
                AssistantConversationRecord.id == conversation_id
            )
        )
    assert owner == owner_user_id

    await engine.dispose()


async def test_store_appends_completed_exchange_atomically() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    store = ConversationStore(session_factory=create_session_factory(engine))
    conversation_id = uuid4()
    owner_user_id = uuid4()
    created_at = datetime.now(UTC)

    await store.claim_or_validate(conversation_id, owner_user_id, created_at)
    await store.append_completed_exchange(
        conversation_id=conversation_id,
        owner_user_id=owner_user_id,
        user_turn=ConversationTurn(
            role="user",
            content="Question",
            created_at_utc=created_at,
        ),
        assistant_turn=ConversationTurn(
            role="assistant",
            content="Answer",
            created_at_utc=created_at + timedelta(seconds=1),
        ),
    )

    assert await store.read_recent(conversation_id, owner_user_id) == [
        ConversationTurn(role="user", content="Question", created_at_utc=created_at),
        ConversationTurn(
            role="assistant",
            content="Answer",
            created_at_utc=created_at + timedelta(seconds=1),
        ),
    ]
    async with engine.begin() as connection:
        conversation = (
            await connection.execute(
                select(
                    AssistantConversationRecord.owner_user_id,
                    AssistantConversationRecord.turn_count,
                ).where(AssistantConversationRecord.id == conversation_id)
            )
        ).one()
    assert conversation == (owner_user_id, 2)

    await engine.dispose()


async def test_store_persists_and_reads_owner_scoped_evidence() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    store = ConversationStore(session_factory=create_session_factory(engine))
    conversation_id = uuid4()
    owner_user_id = uuid4()
    created_at = datetime.now(UTC)
    await store.claim_or_validate(conversation_id, owner_user_id, created_at)
    snapshot = ConversationEvidenceSnapshot(
        conversation_id=conversation_id,
        owner_user_id=owner_user_id,
        exchange_id=uuid4(),
        tool_name="get_work_orders",
        evidence=(),
        created_at_utc=created_at,
        expires_at_utc=created_at + timedelta(days=90),
    )

    await store.append_completed_exchange(
        conversation_id=conversation_id,
        owner_user_id=owner_user_id,
        user_turn=ConversationTurn("user", "Question", created_at),
        assistant_turn=ConversationTurn("assistant", "Answer", created_at),
        evidence=snapshot,
    )

    assert await store.read_recent_evidence(conversation_id, owner_user_id) == [snapshot]
    with pytest.raises(ConversationOwnershipError):
        await store.read_recent_evidence(conversation_id, uuid4())
    async with engine.begin() as connection:
        assert await connection.scalar(
            select(ConversationEvidenceRecord.id).where(
                ConversationEvidenceRecord.exchange_id == snapshot.exchange_id
            )
        ) is not None

    await engine.dispose()
