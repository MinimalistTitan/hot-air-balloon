from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.assistant.infrastructure.tool_gateway.models import (
    AssistantToolTraceEvent,
)
from app.modules.assistant.tool_gateway.domain import ToolTraceEvent


class ToolTraceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, event: ToolTraceEvent) -> None:
        self._session.add(
            AssistantToolTraceEvent(
                tool_name=event.tool_name,
                actor=event.actor,
                conversation_id=event.conversation_id,
                event=event.event,
                payload_json=event.payload,
                created_at_utc=event.created_at_utc,
            )
        )
        await self._session.flush()
