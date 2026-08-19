from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UploadDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    sha256_hex: str
    blob_url: str
    status: str
    created_at: datetime