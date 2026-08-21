import asyncio
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select

from app.core.database.database import SessionFactory
from app.core.life_cycle import ManagedResource
from app.modules.assistant.application.ports import VectorIndexPort
from app.modules.assistant.infrastructure.conversation_memory.long_term.models import (
    AssistantMemoryRecord,
)


@dataclass(slots=True)
class ReconciliationJob(ManagedResource):
    session_factory: SessionFactory
    vector_index: VectorIndexPort
    namespaces: tuple[str, ...]
    interval_seconds: float
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event, init=False, repr=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="vector-reconciliation-job")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def reconcile_once(self) -> int:
        active_ids_by_namespace: defaultdict[str, set[str]] = defaultdict(set)
        async with self.session_factory() as session:
            records = await session.execute(
                select(AssistantMemoryRecord.vector_namespace, AssistantMemoryRecord.vector_id).where(
                    AssistantMemoryRecord.deleted_at.is_(None)
                )
            )
            for namespace, vector_id in records.tuples():
                active_ids_by_namespace[namespace].add(vector_id)

        deleted_count = 0
        for namespace in self.namespaces:
            orphan_ids = await self.vector_index.list_ids(namespace) - active_ids_by_namespace[namespace]
            if orphan_ids:
                await self.vector_index.delete_ids(namespace, sorted(orphan_ids))
                deleted_count += len(orphan_ids)
        return deleted_count

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            await self.reconcile_once()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                continue
