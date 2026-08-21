import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import SessionFactory
from app.core.life_cycle import ManagedResource
from app.modules.assistant.application.ports import (
    ConversationTurn,
    LongTermMemoryPort,
    MemoryRecordWrite,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.llm_summarizer import (
    ConversationSummary,
)
from app.modules.assistant.infrastructure.conversation_memory.models import (
    AssistantConversationRecord,
    ConversationTurnRecord,
)
from app.modules.assistant.infrastructure.tool_gateway.models import AssistantToolAuditRecord


class ConversationSummarizerPort(Protocol):
    async def summarize(self, turns: list[ConversationTurn]) -> ConversationSummary: ...


@dataclass(slots=True)
class ConsolidationWorker(ManagedResource):
    session_factory: SessionFactory
    summarizer: ConversationSummarizerPort
    memory_store: LongTermMemoryPort
    tool_permissions_by_name: dict[str, str]
    idle_minutes: int
    summary_retention_days: int
    poll_interval_seconds: float = 30.0
    batch_size: int = 20
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event, init=False, repr=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="conversation-consolidation-worker")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def consolidate_once(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(minutes=self.idle_minutes)
        processed = 0

        async with self.session_factory() as session:
            statement = (
                select(AssistantConversationRecord)
                .where(AssistantConversationRecord.consolidated_at.is_(None))
                .where(AssistantConversationRecord.last_turn_at <= cutoff)
                .where(AssistantConversationRecord.turn_count >= 2)
                .order_by(AssistantConversationRecord.last_turn_at.asc())
                .limit(self.batch_size)
                .with_for_update(skip_locked=True)
            )
            conversations = list((await session.scalars(statement)).all())

            for conversation in conversations:
                turns = list(
                    (
                        await session.scalars(
                            select(ConversationTurnRecord)
                            .where(ConversationTurnRecord.conversation_id == conversation.id)
                            .order_by(ConversationTurnRecord.created_at.asc(), ConversationTurnRecord.id.asc())
                        )
                    ).all()
                )
                if len(turns) < 2 or conversation.owner_user_id is None:
                    conversation.consolidated_at = datetime.now(UTC)
                    processed += 1
                    continue

                summary = await self.summarizer.summarize(
                    [
                        ConversationTurn(
                            role=turn.role,
                            content=turn.content,
                            created_at_utc=turn.created_at,
                        )
                        for turn in turns
                    ]
                )
                required_permissions = await self._required_permissions_for_conversation(
                    session=session,
                    conversation_id=conversation.id,
                )
                expires_at = datetime.now(UTC) + timedelta(days=self.summary_retention_days)
                source_turn_ids = tuple(turn.id for turn in turns)

                for fact in summary.salient_facts:
                    await self.memory_store.record(
                        MemoryRecordWrite(
                            kind="conversation_summary",
                            content=fact,
                            owner_user_id=conversation.owner_user_id,
                            site_code=None,
                            required_permissions=required_permissions,
                            source_turn_ids=source_turn_ids,
                            expires_at_utc=expires_at,
                        )
                    )

                conversation.consolidated_at = datetime.now(UTC)
                processed += 1

            await session.commit()

        return processed

    async def _required_permissions_for_conversation(
        self,
        *,
        session: AsyncSession,
        conversation_id: UUID,
    ) -> frozenset[str]:
        rows = list(
            (
                await session.scalars(
                    select(AssistantToolAuditRecord)
                    .where(AssistantToolAuditRecord.conversation_id == conversation_id)
                    .where(AssistantToolAuditRecord.decision == "approved")
                )
            ).all()
        )
        return frozenset(
            permission
            for row in rows
            for permission in [self.tool_permissions_by_name.get(row.tool_name)]
            if permission is not None
        )

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            if await self.consolidate_once() == 0:
                await asyncio.sleep(self.poll_interval_seconds)
