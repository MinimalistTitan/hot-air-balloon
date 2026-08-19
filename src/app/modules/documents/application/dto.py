from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.documents.domain.entities import Document


@dataclass(frozen=True, slots=True)
class UploadedDocumentDTO:
    id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    sha256_hex: str
    blob_url: str
    status: str
    created_at: datetime

    @classmethod
    def from_entity(cls, doc: Document) -> UploadedDocumentDTO:
        return cls(
            id=doc.id,
            original_filename=doc.original_filename,
            content_type=doc.content_type,
            size_bytes=doc.size_bytes,
            sha256_hex=doc.sha256_hex,
            blob_url=doc.blob_url,
            status=doc.status,
            created_at=doc.created_at,
        )