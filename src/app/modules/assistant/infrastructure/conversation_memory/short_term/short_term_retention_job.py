from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, exists, select

from app.core.database.database import SessionFactory
from app.core.life_cycle import ManagedResource
from app.modules.assistant.infrastructure.conversation_memory.models import (
    AssistantConversationRecord,
    ConversationTurnRecord,
)


@dataclass(slots=True)
class ShortTermRetentionJob(ManagedResource):
    session_factory: SessionFactory
    retention_days: int = 90
    assistant_conversation_retention_days: int = 180

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def purge_expired(self) -> int:
        now = datetime.now(UTC)
        conversation_cutoff = now - timedelta(days=self.assistant_conversation_retention_days)
        async with self.session_factory() as session:
            expired_rows = await session.execute(
                select(ConversationTurnRecord.id).where(
                    ConversationTurnRecord.expires_at.is_not(None),
                    ConversationTurnRecord.expires_at < now,
                )
            )
            expired_ids = [row[0] for row in expired_rows.all()]

            if expired_ids:
                await session.execute(
                    delete(ConversationTurnRecord).where(ConversationTurnRecord.id.in_(expired_ids))
                )

            conversation_ids = await session.execute(
                select(AssistantConversationRecord.id).where(
                    AssistantConversationRecord.last_turn_at < conversation_cutoff,
                    ~exists(
                        select(ConversationTurnRecord.id).where(
                            ConversationTurnRecord.conversation_id == AssistantConversationRecord.id
                        )
                    ),
                )
            )
            stale_conversation_ids = [row[0] for row in conversation_ids.all()]
            if stale_conversation_ids:
                await session.execute(
                    delete(AssistantConversationRecord).where(
                        AssistantConversationRecord.id.in_(stale_conversation_ids)
                    )
                )

            await session.commit()
            return len(expired_ids)
