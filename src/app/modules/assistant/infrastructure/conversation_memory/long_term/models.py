from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import String, Text, Uuid
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, TypeDecorator, TypeEngine

from app.core.database.database import Base
from app.core.sqlalchemy_types import UTCDateTime


class UUIDArray(TypeDecorator[list[UUID]]):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[object]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(cast(TypeEngine[object], ARRAY(Uuid(as_uuid=True))))
        return dialect.type_descriptor(JSON())

    def process_bind_param(
        self,
        value: list[UUID] | None,
        dialect: Dialect,
    ) -> list[UUID] | list[str] | None:
        if value is None or dialect.name == "postgresql":
            return value
        return [str(item) for item in value]

    def process_result_value(
        self,
        value: list[UUID] | list[str] | None,
        dialect: Dialect,
    ) -> list[UUID] | None:
        if value is None:
            return None
        return [item if isinstance(item, UUID) else UUID(item) for item in value]


class AssistantMemoryRecord(Base):
    __tablename__ = "assistant_memory_records"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), index=True, nullable=True)
    site_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    required_permissions: Mapped[list[str]] = mapped_column(
        ARRAY(String()).with_variant(JSON(), "sqlite"),
        nullable=False,
        default=list,
    )
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_turn_ids: Mapped[list[UUID]] = mapped_column(
        UUIDArray(),
        nullable=False,
        default=list,
    )
    source_document_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), index=True, nullable=True)
    vector_namespace: Mapped[str] = mapped_column(String(128), nullable=False)
    vector_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    sync_retry_count: Mapped[int] = mapped_column(nullable=False, default=0)
    sync_last_error: Mapped[str | None] = mapped_column(Text(), nullable=True)
