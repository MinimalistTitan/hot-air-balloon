from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.domain.entities import Document
from app.modules.documents.infrastructure.models.models import DocumentRecord, OutboxRecord


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_idempotency_key(self, idempotency_key: str) -> Document | None:
        stmt: Select[tuple[DocumentRecord]] = select(DocumentRecord).where(
            DocumentRecord.idempotency_key == idempotency_key
        )
        record = (await self._session.execute(stmt)).scalar_one_or_none()
        if record is None:
            return None
        return Document(
            id=record.id,
            original_filename=record.original_filename,
            content_type=record.content_type,
            size_bytes=record.size_bytes,
            sha256_hex=record.sha256_hex,
            blob_container=record.blob_container,
            blob_name=record.blob_name,
            blob_url=record.blob_url,
            blob_etag=record.blob_etag,
            status=record.status,
            site_code=record.site_code,
            created_at=record.created_at,
            idempotency_key=record.idempotency_key,
        )

    async def add(self, doc: Document) -> None:
        self._session.add(
            DocumentRecord(
                id=doc.id,
                original_filename=doc.original_filename,
                content_type=doc.content_type,
                size_bytes=doc.size_bytes,
                sha256_hex=doc.sha256_hex,
                blob_container=doc.blob_container,
                blob_name=doc.blob_name,
                blob_url=doc.blob_url,
                blob_etag=doc.blob_etag,
                status=doc.status,
                site_code=doc.site_code,
                idempotency_key=doc.idempotency_key,
                created_at=doc.created_at,
            )
        )
        await self._session.flush()


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        topic: str,
        key: str,
        payload: dict[str, object],
        headers: dict[str, str],
        created_at: datetime,
    ) -> None:
        self._session.add(
            OutboxRecord(
                topic=topic,
                key=key,
                payload_json=payload,
                headers_json=headers,
                created_at=created_at,
            )
        )
        await self._session.flush()
