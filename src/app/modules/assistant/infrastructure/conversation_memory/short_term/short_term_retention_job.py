import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import delete, exists, select

from app.core.database.database import SessionFactory
from app.core.life_cycle import ManagedResource
from app.modules.assistant.application.ports import CheckpointErasePort
from app.modules.assistant.infrastructure.conversation_memory.models import (
    AssistantConversationRecord,
    ConversationTurnRecord,
)

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class ShortTermRetentionJob(ManagedResource):
    session_factory: SessionFactory
    retention_days: int = 90
    assistant_conversation_retention_days: int = 180
    purge_interval_seconds: float = 86_400.0
    checkpoint_eraser: CheckpointErasePort | None = None

    _stop_event: asyncio.Event = field(
        default_factory=asyncio.Event,
        init=False,
        repr=False,
    )

    _task: asyncio.Task[None] | None = field(
        default=None,
        init=False,
        repr=False,
    )

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._run(),
            name="short-term-retention-job",
        )

    async def stop(self) -> None:
        self._stop_event.set()

        if self._task is not None:
            await self._task
            self._task = None

    async def purge_expired(self) -> int:
        now = datetime.now(UTC)
        conversation_cutoff = now - timedelta(days=self.assistant_conversation_retention_days)

        async with self.session_factory() as session:
            expired_rows = (
                await session.execute(
                    select(
                        ConversationTurnRecord.id,
                        ConversationTurnRecord.owner_user_id,
                        ConversationTurnRecord.conversation_id,
                    ).where(
                        ConversationTurnRecord.expires_at.is_not(None),
                        ConversationTurnRecord.expires_at < now,
                    )
                )
            ).all()
            expired_ids = [row.id for row in expired_rows]

            if expired_ids:
                await session.execute(
                    delete(ConversationTurnRecord).where(ConversationTurnRecord.id.in_(expired_ids))
                )

            conversation_rows = (
                await session.execute(
                    select(
                        AssistantConversationRecord.id,
                        AssistantConversationRecord.owner_user_id,
                    ).where(
                        AssistantConversationRecord.last_turn_at < conversation_cutoff,
                        ~exists(
                            select(ConversationTurnRecord.id).where(
                                ConversationTurnRecord.conversation_id
                                == AssistantConversationRecord.id
                            )
                        ),
                    )
                )
            ).all()
            stale_conversation_ids = [row.id for row in conversation_rows]

            affected_conversations: set[tuple[UUID, UUID]] = {
                (row.owner_user_id, row.conversation_id) for row in expired_rows
            }
            affected_conversations.update((row.owner_user_id, row.id) for row in conversation_rows)
            await self._erase_checkpoints(affected_conversations)

            if stale_conversation_ids:
                await session.execute(
                    delete(AssistantConversationRecord).where(
                        AssistantConversationRecord.id.in_(stale_conversation_ids)
                    )
                )

            await session.commit()

            logger.info(
                "short_term_retention_completed",
                deleted_turns=len(expired_ids),
                deleted_conversations=len(stale_conversation_ids),
                erased_checkpoint_threads=len(affected_conversations),
            )

            return len(expired_ids)

    async def _erase_checkpoints(
        self,
        conversations: set[tuple[UUID, UUID]],
    ) -> None:
        if self.checkpoint_eraser is None:
            return

        for owner_user_id, conversation_id in sorted(
            conversations,
            key=lambda item: (item[0].int, item[1].int),
        ):
            await self.checkpoint_eraser.erase_conversation(
                owner_user_id,
                conversation_id,
            )

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.purge_expired()
            except Exception:
                # A temporary database error must not permanently terminate
                # the background retention job.
                logger.exception("short_term_retention_failed")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.purge_interval_seconds,
                )
            except TimeoutError:
                # The configured interval elapsed; perform another purge.
                continue
