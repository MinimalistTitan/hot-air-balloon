from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.documents.infrastructure.models.models import OutboxRecord
from app.shared.messaging.kafka.kafka_callout import MessagePublisher


class OutboxPublisher:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        publisher: MessagePublisher,
        batch_size: int,
        poll_interval_seconds: float,
        max_retries: int,
    ) -> None:
        self._session_factory = session_factory
        self._publisher = publisher
        self._batch_size = batch_size
        self._poll_interval_seconds = poll_interval_seconds
        self._max_retries = max_retries
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="outbox-publisher")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
        await self._publisher.flush()

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            processed = await self._publish_batch()
            if processed == 0:
                await asyncio.sleep(self._poll_interval_seconds)

    async def _publish_batch(self) -> int:
        async with self._session_factory() as session:
            stmt = (
                select(OutboxRecord)
                .where(OutboxRecord.published_at.is_(None))
                .where(OutboxRecord.retry_count < self._max_retries)
                .order_by(OutboxRecord.id.asc())
                .limit(self._batch_size)
                .with_for_update(skip_locked=True)
            )
            rows = (await session.execute(stmt)).scalars().all()
            if not rows:
                return 0

            for row in rows:
                try:
                    await self._publisher.publish(
                        topic=row.topic,
                        key=row.key,
                        payload=row.payload_json,
                        headers=row.headers_json,
                    )
                    row.published_at = datetime.now(UTC)
                    row.last_error = None
                except Exception as exc:
                    row.retry_count += 1
                    row.last_error = str(exc)[:4000]
                    await asyncio.sleep(
                        min(2.0, 0.05 * (2**row.retry_count)) + random.random() * 0.05 #noqa: S311
                    )

            await session.commit()
            return len(rows)