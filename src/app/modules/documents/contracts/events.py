from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DocumentUploadedV1:
    event_type: str
    event_version: int
    document_id: UUID
    blob_container: str
    blob_name: str
    blob_url: str
    content_type: str
    size_bytes: int
    sha256_hex: str
    uploaded_at: datetime
    request_id: str | None

    @classmethod
    def from_document(
        cls,
        *,
        document_id: UUID,
        blob_container: str,
        blob_name: str,
        blob_url: str,
        content_type: str,
        size_bytes: int,
        sha256_hex: str,
        uploaded_at: datetime,
        request_id: str | None,
    ) -> DocumentUploadedV1:
        return cls(
            event_type="document.uploaded",
            event_version=1,
            document_id=document_id,
            blob_container=blob_container,
            blob_name=blob_name,
            blob_url=blob_url,
            content_type=content_type,
            size_bytes=size_bytes,
            sha256_hex=sha256_hex,
            uploaded_at=uploaded_at,
            request_id=request_id,
        )

    def to_dict(self) -> dict[str, object]:
        #return asdict(self)
        return {
            "event_type": self.event_type,
            "event_version": self.event_version,
            "document_id": str(self.document_id),
            "blob_container": self.blob_container,
            "blob_name": self.blob_name,
            "blob_url": self.blob_url,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "sha256_hex": self.sha256_hex,
            "uploaded_at": self.uploaded_at.isoformat(),
            "request_id": self.request_id,
    }