from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.modules.documents.domain.entities import Document


@dataclass(frozen=True, slots=True)
class BlobUploadResult:
    container: str
    blob_name: str
    blob_url: str
    etag: str
    
class BlobStoragePort(Protocol):
    async def upload(
        self,
        *,
        document_id: UUID,
        filename: str,
        content_type: str,
        payload: bytes,
        sha256_hex: str,
    ) -> BlobUploadResult: ...
    
class DocumentRepository(Protocol):
    async def get_by_idempotency_key(self, idempotency_key: str) -> Document | None: ...
    async def add(self, doc: Document) -> None: ...
    
class OutboxRepository(Protocol):
    async def add(
        self,
        *,
        topic: str,
        key: str,
        payload: dict[str, object],
        headers: dict[str, str],
        created_at: datetime,
    ) -> None: ...
    
class DocumentUnitOfWork(Protocol):
    @property
    def documents(self) -> DocumentRepository: ...

    @property
    def outbox(self) -> OutboxRepository: ...

    async def __aenter__(self) -> Self: ...
    async def __aexit__(
        self, 
        exc_type: type[BaseException] | None, 
        exc_value: BaseException | None, 
        traceback: TracebackType | None
    ) -> None: ...
    async def commit(self) -> None: ...


type DocumentsUnitOfWorkFactory = Callable[[], DocumentUnitOfWork]