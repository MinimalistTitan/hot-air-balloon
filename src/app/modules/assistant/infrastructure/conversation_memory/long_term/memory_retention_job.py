import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select

from app.core.database.database import SessionFactory
from app.core.life_cycle import ManagedResource
from app.modules.assistant.application.ports import VectorIndexPort
from app.modules.assistant.infrastructure.conversation_memory.long_term.models import (
    AssistantMemoryCandidate,
    AssistantMemoryRecord,
)


@dataclass(frozen=True, slots=True)
class MemoryRetentionResult:
    soft_deleted_records: int
    hard_deleted_records: int
    deleted_vectors: int
    deleted_candidates: int


@dataclass(slots=True)
class MemoryRetentionJob(ManagedResource):
    session_factory: SessionFactory
    vector_index: VectorIndexPort
    batch_size: int
    poll_interval_seconds: float
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event, init=False, repr=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="memory-retention-job")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def purge_once(self) -> MemoryRetentionResult:
        now = datetime.now(UTC)
        soft_deleted_records = await self._soft_delete_expired(now=now)
        hard_deleted_records, deleted_vectors = await self._delete_soft_deleted_batch()
        deleted_candidates = await self._delete_expired_candidates(now=now)
        return MemoryRetentionResult(
            soft_deleted_records=soft_deleted_records,
            hard_deleted_records=hard_deleted_records,
            deleted_vectors=deleted_vectors,
            deleted_candidates=deleted_candidates,
        )

    async def _delete_expired_candidates(self, *, now: datetime) -> int:
        async with self.session_factory() as session:
            candidates = list(
                (
                    await session.scalars(
                        select(AssistantMemoryCandidate)
                        .where(AssistantMemoryCandidate.expires_at < now)
                        .order_by(AssistantMemoryCandidate.created_at.asc())
                        .limit(self.batch_size)
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )
            for candidate in candidates:
                await session.delete(candidate)
            await session.commit()
        return len(candidates)

    async def _soft_delete_expired(self, *, now: datetime) -> int:
        async with self.session_factory() as session:
            expired_rows = list(
                (
                    await session.scalars(
                        select(AssistantMemoryRecord)
                        .where(AssistantMemoryRecord.deleted_at.is_(None))
                        .where(AssistantMemoryRecord.expires_at.is_not(None))
                        .where(AssistantMemoryRecord.expires_at < now)
                        .order_by(AssistantMemoryRecord.created_at.asc())
                        .limit(self.batch_size)
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )
            if not expired_rows:
                return 0

            for row in expired_rows:
                row.deleted_at = now

            await session.commit()
            return len(expired_rows)

    async def _delete_soft_deleted_batch(self) -> tuple[int, int]:
        async with self.session_factory() as session:
            soft_deleted_rows = list(
                (
                    await session.scalars(
                        select(AssistantMemoryRecord)
                        .where(AssistantMemoryRecord.deleted_at.is_not(None))
                        .order_by(
                            AssistantMemoryRecord.deleted_at.asc(), AssistantMemoryRecord.id.asc()
                        )
                        .limit(self.batch_size)
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )

        if not soft_deleted_rows:
            return 0, 0

        grouped_ids: defaultdict[str, list[str]] = defaultdict(list)
        row_ids_by_namespace: defaultdict[str, list[UUID]] = defaultdict(list)
        for row in soft_deleted_rows:
            grouped_ids[row.vector_namespace].append(row.vector_id)
            row_ids_by_namespace[row.vector_namespace].append(row.id)

        deletable_row_ids: list[UUID] = []
        deleted_vectors = 0
        for namespace, vector_ids in grouped_ids.items():
            await self.vector_index.delete_ids(namespace, vector_ids)
            deleted_vectors += len(vector_ids)
            deletable_row_ids.extend(row_ids_by_namespace[namespace])

        if not deletable_row_ids:
            return 0, deleted_vectors

        async with self.session_factory() as session:
            await session.execute(
                delete(AssistantMemoryRecord).where(AssistantMemoryRecord.id.in_(deletable_row_ids))
            )
            await session.commit()

        return len(deletable_row_ids), deleted_vectors

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            await self.purge_once()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval_seconds)
            except TimeoutError:
                continue
