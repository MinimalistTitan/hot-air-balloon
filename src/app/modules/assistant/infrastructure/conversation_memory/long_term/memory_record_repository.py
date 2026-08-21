from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.database.database import SessionFactory
from app.modules.assistant.application.ports import (
    LongTermMemoryPort,
    MemoryRecordWrite,
    UserMemoryReaderPort,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.models import (
    AssistantMemoryRecord,
)


@dataclass(slots=True)
class MemoryRecordRepository(LongTermMemoryPort, UserMemoryReaderPort):
    session_factory: SessionFactory
    embedding_model: str
    user_memory_namespace: str
    documents_namespace: str

    async def record(self, memory: MemoryRecordWrite) -> UUID:
        memory_id = uuid4()
        async with self.session_factory() as session:
            session.add(
                AssistantMemoryRecord(
                    id=memory_id,
                    kind=memory.kind,
                    owner_user_id=memory.owner_user_id,
                    site_code=memory.site_code,
                    required_permissions=sorted(memory.required_permissions),
                    content=memory.content,
                    content_sha256=sha256(memory.content.encode()).hexdigest(),
                    source_turn_ids=list(memory.source_turn_ids),
                    source_document_id=memory.source_document_id,
                    vector_namespace=self._namespace_for(memory.kind),
                    vector_id=str(memory_id),
                    embedding_model=self.embedding_model,
                    created_at=datetime.now(UTC),
                    expires_at=memory.expires_at_utc,
                )
            )
            await session.commit()
        return memory_id

    def _namespace_for(self, kind: str) -> str:
        if kind == "conversation_summary":
            return self.user_memory_namespace
        if kind == "document_chunk":
            return self.documents_namespace
        raise ValueError(f"Unsupported long-term memory kind: {kind}")

    async def read_recent_user_memories(self, owner_user_id: UUID, limit: int) -> list[str]:
        if limit <= 0:
            return []

        async with self.session_factory() as session:
            rows = list(
                (
                    await session.scalars(
                        select(AssistantMemoryRecord)
                        .where(AssistantMemoryRecord.owner_user_id == owner_user_id)
                        .where(AssistantMemoryRecord.kind == "conversation_summary")
                        .where(AssistantMemoryRecord.deleted_at.is_(None))
                        .order_by(AssistantMemoryRecord.created_at.desc())
                        .limit(limit)
                    )
                ).all()
            )

        rows.reverse()
        return [row.content for row in rows]
