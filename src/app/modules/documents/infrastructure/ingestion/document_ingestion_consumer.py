import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.core.database.database import SessionFactory
from app.core.life_cycle import ManagedResource
from app.modules.assistant.application.ports import LongTermMemoryPort, MemoryRecordWrite
from app.modules.documents.infrastructure.ingestion.blob_downloader import BlobDownloaderPort
from app.modules.documents.infrastructure.ingestion.chunker import TokenChunker
from app.modules.documents.infrastructure.ingestion.text_extractor import (
    TextExtractionError,
    TextExtractor,
)
from app.modules.documents.infrastructure.models.models import DocumentRecord, OutboxRecord


@dataclass(slots=True)
class DocumentIngestionConsumer(ManagedResource):
    session_factory: SessionFactory
    blob_downloader: BlobDownloaderPort
    memory_store: LongTermMemoryPort
    text_extractor: TextExtractor
    chunker: TokenChunker
    batch_size: int
    poll_interval_seconds: float
    topic_name: str
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event, init=False, repr=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="document-ingestion-consumer")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def ingest_once(self) -> int:
        processed = 0
        async with self.session_factory() as session:
            statement = (
                select(OutboxRecord)
                .where(OutboxRecord.topic == self.topic_name)
                .where(OutboxRecord.ingested_at.is_(None))
                .order_by(OutboxRecord.id.asc())
                .limit(self.batch_size)
                .with_for_update(skip_locked=True)
            )
            events = list((await session.scalars(statement)).all())
            for event in events:
                document_id = UUID(event.key)
                document = await session.get(DocumentRecord, document_id)
                if document is None:
                    event.ingested_at = datetime.now(UTC)
                    continue
                document.status = "ingesting"
                try:
                    payload = await self.blob_downloader.download(
                        container=document.blob_container,
                        blob_name=document.blob_name,
                    )
                    text = self.text_extractor.extract(
                        content_type=document.content_type,
                        payload=payload,
                    )
                except TextExtractionError as exception:
                    document.status = "failed"
                    document.ingestion_error = str(exception)[:4000]
                    event.ingested_at = datetime.now(UTC)
                    processed += 1
                    continue

                for chunk in self.chunker.chunk(text):
                    await self.memory_store.record(
                        MemoryRecordWrite(
                            kind="document_chunk",
                            content=chunk,
                            owner_user_id=None,
                            site_code=None,
                            required_permissions=frozenset({"documents:read"}),
                            source_document_id=document.id,
                        )
                    )
                document.status = "indexed"
                document.ingestion_error = None
                event.ingested_at = datetime.now(UTC)
                processed += 1
            await session.commit()
        return processed

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            if await self.ingest_once() == 0:
                await asyncio.sleep(self.poll_interval_seconds)
