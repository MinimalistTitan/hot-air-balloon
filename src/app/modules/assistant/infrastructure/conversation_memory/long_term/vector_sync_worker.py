import asyncio
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.database.database import SessionFactory
from app.core.life_cycle import ManagedResource
from app.modules.assistant.application.ports import EmbeddingPort, VectorIndexPort, VectorRecord
from app.modules.assistant.infrastructure.conversation_memory.long_term.models import (
    AssistantMemoryRecord,
)


@dataclass(slots=True)
class VectorSyncWorker(ManagedResource):
    session_factory: SessionFactory
    embedding_client: EmbeddingPort
    vector_index: VectorIndexPort
    batch_size: int
    poll_interval_seconds: float
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event, init=False, repr=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="vector-sync-worker")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def sync_once(self) -> int:
        async with self.session_factory() as session:
            statement = (
                select(AssistantMemoryRecord)
                .where(AssistantMemoryRecord.synced_at.is_(None))
                .where(AssistantMemoryRecord.deleted_at.is_(None))
                .order_by(AssistantMemoryRecord.created_at.asc())
                .limit(self.batch_size)
                .with_for_update(skip_locked=True)
            )
            records = list((await session.scalars(statement)).all())
            for record in records:
                try:
                    embedding = await self.embedding_client.embed(record.content)
                    await self.vector_index.upsert(
                        record.vector_namespace,
                        [
                            VectorRecord(
                                vector_id=record.vector_id,
                                values=embedding,
                                metadata={
                                    "kind": record.kind,
                                    "owner_user_id": (
                                        str(record.owner_user_id)
                                        if record.owner_user_id is not None
                                        else None
                                    ),
                                    "site_code": record.site_code,
                                    "required_permissions": record.required_permissions,
                                    "source_document_id": (
                                        str(record.source_document_id)
                                        if record.source_document_id is not None
                                        else None
                                    ),
                                    "memory_record_id": str(record.id),
                                    "created_at_epoch": int(record.created_at.timestamp()),
                                },
                            )
                        ],
                    )
                    record.synced_at = datetime.now(UTC)
                    record.sync_last_error = None
                except Exception as exception:
                    record.sync_retry_count += 1
                    record.sync_last_error = str(exception)[:4000]
                    await asyncio.sleep(
                        min(2.0, 0.05 * (2**record.sync_retry_count))
                        + random.random() * 0.05  # noqa: S311
                    )
            await session.commit()
            return len(records)

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            if await self.sync_once() == 0:
                await asyncio.sleep(self.poll_interval_seconds)
