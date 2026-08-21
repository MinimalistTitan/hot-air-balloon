from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database.database import Base, create_session_factory
from app.modules.assistant.application.ports import MemoryRecordWrite
from app.modules.documents.infrastructure.ingestion.chunker import TokenChunker
from app.modules.documents.infrastructure.ingestion.document_ingestion_consumer import (
    DocumentIngestionConsumer,
)
from app.modules.documents.infrastructure.ingestion.text_extractor import TextExtractor
from app.modules.documents.infrastructure.models.models import DocumentRecord, OutboxRecord


class FakeBlobDownloader:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    async def download(self, *, container: str, blob_name: str) -> bytes:
        assert container == "documents"
        assert blob_name == "uploads/handbook.txt"
        return self.payload


class FakeMemoryStore:
    def __init__(self) -> None:
        self.memories: list[MemoryRecordWrite] = []

    async def record(self, memory: MemoryRecordWrite) -> object:
        self.memories.append(memory)
        return uuid4()


async def test_consumer_indexes_document_and_records_chunks() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    document_id = uuid4()
    async with session_factory() as session:
        session.add(
            DocumentRecord(
                id=document_id,
                original_filename="handbook.txt",
                content_type="text/plain",
                size_bytes=61,
                sha256_hex="a" * 64,
                blob_container="documents",
                blob_name="uploads/handbook.txt",
                blob_url="https://example.test/handbook.txt",
                blob_etag="etag",
                status="queued",
                created_at=datetime.now(UTC),
            )
        )
        session.add(
            OutboxRecord(
                topic="document.uploaded.v1",
                key=str(document_id),
                payload_json={},
                headers_json={},
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()

    memory_store = FakeMemoryStore()
    consumer = DocumentIngestionConsumer(
        session_factory=session_factory,
        blob_downloader=FakeBlobDownloader(b"Maintenance reports are reviewed every morning."),
        memory_store=memory_store,
        text_extractor=TextExtractor(),
        chunker=TokenChunker(chunk_tokens=50, overlap_tokens=10),
        batch_size=10,
        poll_interval_seconds=1.0,
        topic_name="document.uploaded.v1",
    )

    assert await consumer.ingest_once() == 1
    assert [memory.kind for memory in memory_store.memories] == ["document_chunk"]
    assert memory_store.memories[0].source_document_id == document_id
    assert memory_store.memories[0].required_permissions == frozenset({"documents:read"})

    async with session_factory() as session:
        document = await session.get(DocumentRecord, document_id)
        event = await session.scalar(select(OutboxRecord).where(OutboxRecord.key == str(document_id)))

    assert document is not None
    assert document.status == "indexed"
    assert document.ingestion_error is None
    assert event is not None
    assert event.ingested_at is not None
    await engine.dispose()


async def test_consumer_marks_invalid_text_as_failed() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    document_id = uuid4()
    async with session_factory() as session:
        session.add(
            DocumentRecord(
                id=document_id,
                original_filename="invalid.txt",
                content_type="text/plain",
                size_bytes=1,
                sha256_hex="b" * 64,
                blob_container="documents",
                blob_name="uploads/handbook.txt",
                blob_url="https://example.test/invalid.txt",
                blob_etag="etag",
                status="queued",
                created_at=datetime.now(UTC),
            )
        )
        session.add(
            OutboxRecord(
                topic="document.uploaded.v1",
                key=str(document_id),
                payload_json={},
                headers_json={},
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()

    memory_store = FakeMemoryStore()
    consumer = DocumentIngestionConsumer(
        session_factory=session_factory,
        blob_downloader=FakeBlobDownloader(b"\xff"),
        memory_store=memory_store,
        text_extractor=TextExtractor(),
        chunker=TokenChunker(chunk_tokens=50, overlap_tokens=10),
        batch_size=10,
        poll_interval_seconds=1.0,
        topic_name="document.uploaded.v1",
    )

    assert await consumer.ingest_once() == 1
    assert memory_store.memories == []

    async with session_factory() as session:
        document = await session.get(DocumentRecord, document_id)
        event = await session.scalar(select(OutboxRecord).where(OutboxRecord.key == str(document_id)))

    assert document is not None
    assert document.status == "failed"
    assert document.ingestion_error == "Document text extraction failed"
    assert event is not None
    assert event.ingested_at is not None
    await engine.dispose()
