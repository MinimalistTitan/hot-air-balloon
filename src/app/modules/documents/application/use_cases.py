from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from app.modules.documents.application.commands import UploadDocumentCommand
from app.modules.documents.application.dto import UploadedDocumentDTO
from app.modules.documents.application.ports import BlobStoragePort, DocumentsUnitOfWorkFactory
from app.modules.documents.contracts.events import DocumentUploadedV1
from app.modules.documents.domain.entities import Document
from app.modules.documents.domain.errors import (
    DocumentAlreadyExistsError,
    StorageUploadFailedError,
)


@dataclass(slots=True)
class UploadDocument:
    unit_of_work_factory: DocumentsUnitOfWorkFactory
    blob_storage: BlobStoragePort
    topic_name: str

    async def execute(self, command: UploadDocumentCommand) -> UploadedDocumentDTO:
        checksum = sha256(command.content_bytes).hexdigest()
        now = datetime.now(UTC)
        temp_document = Document.create(
            original_filename=command.original_filename,
            content_type=command.content_type,
            size_bytes=len(command.content_bytes),
            sha256_hex=checksum,
            blob_container="pending",
            blob_name="pending",
            blob_url="pending",
            blob_etag="pending",
            idempotency_key=command.idempotency_key,
            now=now,
        )

        try:
            upload_result = await self.blob_storage.upload(
                document_id=temp_document.id,
                filename=command.original_filename,
                content_type=command.content_type,
                payload=command.content_bytes,
                sha256_hex=checksum,
            )
        except Exception as exc:
            raise StorageUploadFailedError("blob upload failed") from exc

        document = Document.create(
            document_id=temp_document.id,
            original_filename=command.original_filename,
            content_type=command.content_type,
            size_bytes=len(command.content_bytes),
            sha256_hex=checksum,
            blob_container=upload_result.container,
            blob_name=upload_result.blob_name,
            blob_url=upload_result.blob_url,
            blob_etag=upload_result.etag,
            idempotency_key=command.idempotency_key,
            now=now,
        )

        event = DocumentUploadedV1.from_document(
            document_id=document.id,
            blob_container=document.blob_container,
            blob_name=document.blob_name,
            blob_url=document.blob_url,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            sha256_hex=document.sha256_hex,
            uploaded_at=document.created_at,
            request_id=command.request_id,
        )

        async with self.unit_of_work_factory() as uow:
            if command.idempotency_key:
                existing = await uow.documents.get_by_idempotency_key(command.idempotency_key)
                if existing is not None:
                    raise DocumentAlreadyExistsError("idempotency key already used")

            await uow.documents.add(document)
            await uow.outbox.add(
                topic=self.topic_name,
                key=str(document.id),
                payload=event.to_dict(),
                headers={
                    "event_type": "document.uploaded",
                    "event_version": "1",
                    "content_type": "application/json",
                },
                created_at=now,
            )
            await uow.commit()

        return UploadedDocumentDTO.from_entity(document)