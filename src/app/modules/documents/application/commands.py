from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UploadDocumentCommand:
    original_filename: str
    content_type: str
    content_bytes: bytes
    request_id: str | None
    idempotency_key: str | None = None