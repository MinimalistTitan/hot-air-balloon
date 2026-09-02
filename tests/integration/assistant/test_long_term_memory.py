from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database.database import Base, create_session_factory
from app.modules.assistant.application.ports import MemoryRecordWrite, VectorRecord
from app.modules.assistant.infrastructure.conversation_memory.long_term.memory_record_repository import (
    MemoryRecordRepository,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.memory_retention_job import (
    MemoryRetentionJob,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.models import (
    AssistantMemoryRecord,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.reconciliation_job import (
    ReconciliationJob,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.user_memory_eraser import (
    UserMemoryEraser,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.vector_sync_worker import (
    VectorSyncWorker,
)
from app.modules.assistant.infrastructure.conversation_memory.models import (
    AssistantConversationRecord,
    ConversationTurnRecord,
)


class FakeEmbeddingClient:
    async def embed(self, text: str) -> list[float]:
        assert text == "User prefers morning maintenance reports."
        return [0.1, 0.2, 0.3]


class FakeVectorIndex:
    def __init__(self) -> None:
        self.upserts: list[tuple[str, list[VectorRecord]]] = []
        self.ids_by_namespace: dict[str, set[str]] = {}
        self.deleted_ids: list[tuple[str, list[str]]] = []

    async def upsert(self, namespace: str, records: list[VectorRecord]) -> None:
        self.upserts.append((namespace, records))

    async def fetch_ids(self, namespace: str, vector_ids: list[str]) -> set[str]:
        return set(vector_ids)

    async def query_ids(
        self,
        namespace: str,
        values: list[float],
        limit: int,
        metadata_filter: dict[str, str],
    ) -> list[str]:
        del namespace, values, limit, metadata_filter
        return []

    async def list_ids(self, namespace: str) -> set[str]:
        return self.ids_by_namespace.get(namespace, set())

    async def delete_ids(self, namespace: str, vector_ids: list[str]) -> None:
        self.deleted_ids.append((namespace, vector_ids))


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


async def test_repository_persists_lineage_and_user_memory_namespace() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    repository = MemoryRecordRepository(
        session_factory=session_factory,
        embedding_model="text-embedding-3-small",
        user_memory_namespace="user-memory",
        documents_namespace="documents",
    )
    owner_user_id = uuid4()
    source_turn_id = uuid4()

    memory_id = await repository.record(
        MemoryRecordWrite(
            kind="conversation_summary",
            content="User prefers morning maintenance reports.",
            owner_user_id=owner_user_id,
            site_code="plant-a",
            required_permissions=frozenset({"reports:read"}),
            source_turn_ids=(source_turn_id,),
        )
    )

    async with session_factory() as session:
        record = await session.scalar(
            select(AssistantMemoryRecord).where(AssistantMemoryRecord.id == memory_id)
        )

    assert record is not None
    assert record.owner_user_id == owner_user_id
    assert record.source_turn_ids == [source_turn_id]
    assert record.vector_namespace == "user-memory"
    assert record.vector_id == str(memory_id)
    assert record.synced_at is None
    await engine.dispose()


async def test_sync_worker_upserts_pending_memory_and_marks_it_synced() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    vector_index = FakeVectorIndex()
    memory_id = uuid4()
    created_at = datetime.now(UTC)
    async with session_factory() as session:
        session.add(
            AssistantMemoryRecord(
                id=memory_id,
                kind="conversation_summary",
                owner_user_id=uuid4(),
                site_code=None,
                required_permissions=["reports:read"],
                content="User prefers morning maintenance reports.",
                content_sha256="a" * 64,
                source_turn_ids=[],
                source_document_id=None,
                vector_namespace="user-memory",
                vector_id=str(memory_id),
                embedding_model="text-embedding-3-small",
                created_at=created_at,
                expires_at=None,
            )
        )
        await session.commit()

    worker = VectorSyncWorker(
        session_factory=session_factory,
        embedding_client=FakeEmbeddingClient(),
        vector_index=vector_index,
        batch_size=10,
        poll_interval_seconds=1.0,
    )

    assert await worker.sync_once() == 1
    assert len(vector_index.upserts) == 1
    namespace, records = vector_index.upserts[0]
    assert namespace == "user-memory"
    assert records[0].vector_id == str(memory_id)
    assert records[0].metadata["memory_record_id"] == str(memory_id)

    async with session_factory() as session:
        record = await session.scalar(
            select(AssistantMemoryRecord).where(AssistantMemoryRecord.id == memory_id)
        )

    assert record is not None
    assert record.synced_at is not None
    assert record.sync_last_error is None
    await engine.dispose()


async def test_reconciliation_deletes_only_orphaned_vectors() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    memory_id = uuid4()
    async with session_factory() as session:
        session.add(
            AssistantMemoryRecord(
                id=memory_id,
                kind="conversation_summary",
                owner_user_id=uuid4(),
                site_code=None,
                required_permissions=[],
                content="User prefers morning maintenance reports.",
                content_sha256="a" * 64,
                source_turn_ids=[],
                source_document_id=None,
                vector_namespace="user-memory",
                vector_id=str(memory_id),
                embedding_model="text-embedding-3-small",
                created_at=datetime.now(UTC),
                expires_at=None,
            )
        )
        await session.commit()

    vector_index = FakeVectorIndex()
    vector_index.ids_by_namespace = {
        "user-memory": {str(memory_id), "orphan-vector"},
        "documents": {"orphan-document"},
    }
    job = ReconciliationJob(
        session_factory=session_factory,
        vector_index=vector_index,
        namespaces=("user-memory", "documents"),
        interval_seconds=86_400.0,
    )

    assert await job.reconcile_once() == 2
    assert vector_index.deleted_ids == [
        ("user-memory", ["orphan-vector"]),
        ("documents", ["orphan-document"]),
    ]
    await engine.dispose()


async def test_memory_retention_soft_deletes_then_hard_deletes() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    expired_id = uuid4()
    async with session_factory() as session:
        session.add(
            AssistantMemoryRecord(
                id=expired_id,
                kind="conversation_summary",
                owner_user_id=uuid4(),
                site_code=None,
                required_permissions=[],
                content="Expired memory",
                content_sha256="b" * 64,
                source_turn_ids=[],
                source_document_id=None,
                vector_namespace="user-memory",
                vector_id=str(expired_id),
                embedding_model="text-embedding-3-small",
                created_at=datetime.now(UTC),
                expires_at=datetime.now(UTC),
            )
        )
        await session.commit()

    vector_index = FakeVectorIndex()
    job = MemoryRetentionJob(
        session_factory=session_factory,
        vector_index=vector_index,
        batch_size=10,
        poll_interval_seconds=1.0,
    )

    result = await job.purge_once()

    assert result.soft_deleted_records == 1
    assert result.hard_deleted_records == 1
    assert result.deleted_vectors == 1
    assert vector_index.deleted_ids == [("user-memory", [str(expired_id)])]
    async with session_factory() as session:
        remaining = await session.scalar(
            select(AssistantMemoryRecord).where(AssistantMemoryRecord.id == expired_id)
        )
    assert remaining is None
    await engine.dispose()


async def test_user_memory_eraser_deletes_memory_vectors_turns_and_conversations() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    owner_user_id = uuid4()
    other_user_id = uuid4()
    conversation_id = uuid4()
    turn_id = uuid4()
    owned_memory_id = uuid4()
    lineage_memory_id = uuid4()
    untouched_memory_id = uuid4()
    now = datetime.now(UTC)

    async with session_factory() as session:
        session.add(
            AssistantConversationRecord(
                id=conversation_id,
                owner_user_id=owner_user_id,
                started_at=now,
                last_turn_at=now,
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
                content="hello",
                created_at=now,
                expires_at=None,
            )
        )
        session.add(
            AssistantMemoryRecord(
                id=owned_memory_id,
                kind="conversation_summary",
                owner_user_id=owner_user_id,
                site_code=None,
                required_permissions=[],
                content="Owned memory",
                content_sha256="c" * 64,
                source_turn_ids=[],
                source_document_id=None,
                vector_namespace="user-memory",
                vector_id=str(owned_memory_id),
                embedding_model="text-embedding-3-small",
                created_at=now,
                expires_at=None,
            )
        )
        session.add(
            AssistantMemoryRecord(
                id=lineage_memory_id,
                kind="conversation_summary",
                owner_user_id=other_user_id,
                site_code=None,
                required_permissions=[],
                content="Lineage memory",
                content_sha256="d" * 64,
                source_turn_ids=[turn_id],
                source_document_id=None,
                vector_namespace="user-memory",
                vector_id=str(lineage_memory_id),
                embedding_model="text-embedding-3-small",
                created_at=now,
                expires_at=None,
            )
        )
        session.add(
            AssistantMemoryRecord(
                id=untouched_memory_id,
                kind="conversation_summary",
                owner_user_id=other_user_id,
                site_code=None,
                required_permissions=[],
                content="Untouched memory",
                content_sha256="e" * 64,
                source_turn_ids=[],
                source_document_id=None,
                vector_namespace="user-memory",
                vector_id=str(untouched_memory_id),
                embedding_model="text-embedding-3-small",
                created_at=now,
                expires_at=None,
            )
        )
        await session.commit()

    vector_index = FakeVectorIndex()
    checkpoint_eraser = RecordingCheckpointEraser()
    eraser = UserMemoryEraser(
        session_factory=session_factory,
        vector_index=vector_index,
        checkpoint_eraser=checkpoint_eraser,
    )

    result = await eraser.erase_user_memory(owner_user_id)

    assert result.deleted_memory_records == 2
    assert result.deleted_vectors == 2
    assert result.deleted_turns == 1
    assert result.deleted_conversations == 1
    assert vector_index.deleted_ids == [
        ("user-memory", [str(owned_memory_id), str(lineage_memory_id)]),
    ]
    assert checkpoint_eraser.calls == [(owner_user_id, conversation_id)]

    async with session_factory() as session:
        remaining_memory_ids = set(
            (
                await session.scalars(
                    select(AssistantMemoryRecord.id).order_by(AssistantMemoryRecord.id.asc())
                )
            ).all()
        )
        remaining_turns = list((await session.scalars(select(ConversationTurnRecord.id))).all())
        remaining_conversations = list(
            (
                await session.scalars(
                    select(AssistantConversationRecord.id)
                )
            ).all()
        )

    assert remaining_memory_ids == {untouched_memory_id}
    assert remaining_turns == []
    assert remaining_conversations == []
    await engine.dispose()


async def test_user_memory_checkpoint_failure_rolls_back_transcript_erasure() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    owner_user_id = uuid4()
    conversation_id = uuid4()
    turn_id = uuid4()
    now = datetime.now(UTC)
    async with session_factory() as session:
        session.add(
            AssistantConversationRecord(
                id=conversation_id,
                owner_user_id=owner_user_id,
                started_at=now,
                last_turn_at=now,
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
                content="keep until checkpoint erasure succeeds",
                created_at=now,
                expires_at=None,
            )
        )
        await session.commit()

    eraser = UserMemoryEraser(
        session_factory=session_factory,
        vector_index=FakeVectorIndex(),
        checkpoint_eraser=RecordingCheckpointEraser(
            failure=RuntimeError("checkpoint database unavailable")
        ),
    )

    with pytest.raises(RuntimeError, match="checkpoint database unavailable"):
        await eraser.erase_user_memory(owner_user_id)

    async with session_factory() as session:
        assert (
            await session.scalar(
                select(ConversationTurnRecord.id).where(ConversationTurnRecord.id == turn_id)
            )
            == turn_id
        )
        assert (
            await session.scalar(
                select(AssistantConversationRecord.id).where(
                    AssistantConversationRecord.id == conversation_id
                )
            )
            == conversation_id
        )
    await engine.dispose()
