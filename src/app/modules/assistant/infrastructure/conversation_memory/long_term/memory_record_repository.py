from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database.database import SessionFactory
from app.modules.assistant.application.ports import (
    LongTermMemoryPort,
    MemoryRecordWrite,
    UserMemoryReaderPort,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.models import (
    AssistantMemoryRecord,
)
from app.modules.user.domain.authorization import AuthorizationContext, Permission


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

    async def record_or_get_user_fact(self, memory: MemoryRecordWrite) -> tuple[UUID, bool]:
        if memory.kind != "conversation_summary" or memory.owner_user_id is None:
            raise ValueError("User fact promotion requires an owned conversation summary")

        content_sha256 = self._content_hash(memory.content)
        async with self.session_factory() as session:
            statement = (
                select(AssistantMemoryRecord)
                .where(AssistantMemoryRecord.owner_user_id == memory.owner_user_id)
                .where(AssistantMemoryRecord.kind == memory.kind)
                .where(AssistantMemoryRecord.content_sha256 == content_sha256)
                .where(AssistantMemoryRecord.deleted_at.is_(None))
                .with_for_update()
            )
            existing = await session.scalar(statement)
            if existing is not None:
                existing.source_turn_ids = list(
                    dict.fromkeys((*existing.source_turn_ids, *memory.source_turn_ids))
                )
                await session.commit()
                return existing.id, False

            memory_id = uuid4()
            session.add(
                AssistantMemoryRecord(
                    id=memory_id,
                    kind=memory.kind,
                    owner_user_id=memory.owner_user_id,
                    site_code=memory.site_code,
                    required_permissions=sorted(memory.required_permissions),
                    content=memory.content.strip(),
                    content_sha256=content_sha256,
                    source_turn_ids=list(memory.source_turn_ids),
                    source_document_id=memory.source_document_id,
                    vector_namespace=self._namespace_for(memory.kind),
                    vector_id=str(memory_id),
                    embedding_model=self.embedding_model,
                    created_at=datetime.now(UTC),
                    expires_at=memory.expires_at_utc,
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                existing = await session.scalar(statement)
                if existing is None:
                    raise
                return existing.id, False
            return memory_id, True

    def _namespace_for(self, kind: str) -> str:
        if kind == "conversation_summary":
            return self.user_memory_namespace
        if kind == "document_chunk":
            return self.documents_namespace
        raise ValueError(f"Unsupported long-term memory kind: {kind}")

    def _content_hash(self, content: str) -> str:
        return sha256(" ".join(content.lower().split()).encode()).hexdigest()

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

    async def read_document_chunks_by_vector_ids(
        self,
        vector_ids: list[str],
        authorization_context: AuthorizationContext,
    ) -> list[str]:
        if not vector_ids or not authorization_context.can(Permission.DOCUMENTS_READ):
            return []

        async with self.session_factory() as session:
            rows = list(
                (
                    await session.scalars(
                        select(AssistantMemoryRecord)
                        .where(AssistantMemoryRecord.kind == "document_chunk")
                        .where(AssistantMemoryRecord.vector_id.in_(vector_ids))
                        .where(AssistantMemoryRecord.deleted_at.is_(None))
                        .where(AssistantMemoryRecord.synced_at.is_not(None))
                    )
                ).all()
            )

        permission_values = {permission.value for permission in authorization_context.permissions}
        allowed_rows = {
            row.vector_id: row
            for row in rows
            if set(row.required_permissions).issubset(permission_values)
            and authorization_context.can(Permission.DOCUMENTS_READ, site_code=row.site_code)
        }
        return [
            allowed_rows[vector_id].content for vector_id in vector_ids if vector_id in allowed_rows
        ]
