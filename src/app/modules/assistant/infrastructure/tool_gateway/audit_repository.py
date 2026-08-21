from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.assistant.infrastructure.tool_gateway.models import AssistantToolAuditRecord
from app.modules.assistant.tool_gateway.domain import ToolAuditRecord


class ToolAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write(self, record: ToolAuditRecord) -> None:
        row = AssistantToolAuditRecord(
            tool_name=record.tool_name,
            actor=record.actor,
            conversation_id=record.conversation_id,
            payload_json=record.payload,
            decision=record.decision.value,
            reason=record.reason,
            created_at_utc=record.created_at_utc or datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()


async def list_recent_records(session: AsyncSession, limit: int = 50) -> list[AssistantToolAuditRecord]:
    query = (
        select(AssistantToolAuditRecord)
        .order_by(AssistantToolAuditRecord.created_at_utc.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    return list(result.scalars().all())
