from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True, kw_only=True)
class Document:
    id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    sha256_hex: str
    blob_container: str
    blob_name: str
    blob_url: str
    blob_etag: str
    status: str
    created_at: datetime
    idempotency_key: str | None

    @classmethod
    def create(
        cls,
        *,
        original_filename: str,
        content_type: str,
        size_bytes: int,
        sha256_hex: str,
        blob_container: str,
        blob_name: str,
        blob_url: str,
        blob_etag: str,
        idempotency_key: str | None = None,
        document_id: UUID | None = None,
        now: datetime | None = None,
    ) -> Document:
        created_at = now or datetime.now(UTC)
        return cls(
            id=document_id or uuid4(),
            original_filename=original_filename.strip(),
            content_type=content_type.strip().lower(),
            size_bytes=size_bytes,
            sha256_hex=sha256_hex,
            blob_container=blob_container,
            blob_name=blob_name,
            blob_url=blob_url,
            blob_etag=blob_etag,
            status="queued",
            created_at=created_at,
            idempotency_key=idempotency_key,
        )