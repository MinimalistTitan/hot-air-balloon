from dataclasses import dataclass

from app.core.config import Settings
from app.core.database.database import SessionFactory
from app.core.life_cycle import ManagedResource
from app.modules.assistant.infrastructure.conversation_memory.long_term.memory_record_repository import (
    MemoryRecordRepository,
)
from app.modules.documents.application.ports import (
    BlobStoragePort,
    DocumentsUnitOfWorkFactory,
)
from app.modules.documents.application.use_cases import UploadDocument
from app.modules.documents.infrastructure.blob_storage import AzureBlobStorage
from app.modules.documents.infrastructure.ingestion.blob_downloader import BlobDownloaderPort
from app.modules.documents.infrastructure.ingestion.chunker import TokenChunker
from app.modules.documents.infrastructure.ingestion.document_ingestion_consumer import (
    DocumentIngestionConsumer,
)
from app.modules.documents.infrastructure.ingestion.text_extractor import TextExtractor
from app.modules.documents.infrastructure.outbox_publisher import (
    OutboxPublisher,
)
from app.modules.documents.infrastructure.unit_of_work import (
    DocumentsUnitOfWork,
)
from app.shared.messaging.kafka.kafka_callout import (
    ConfluentKafkaPublisher,
    MessagePublisher,
)


@dataclass(frozen=True, slots=True)
class DocumentUploadPolicy:
    max_bytes: int
    allowed_content_types: frozenset[str]


@dataclass(frozen=True, slots=True)
class DocumentsModule:
    unit_of_work_factory: DocumentsUnitOfWorkFactory
    upload_document: UploadDocument
    upload_policy: DocumentUploadPolicy
    resources: tuple[ManagedResource, ...]


def build_documents_module(
    settings: Settings,
    session_factory: SessionFactory,
    *,
    blob_storage: BlobStoragePort | None = None,
    publisher: MessagePublisher | None = None,
) -> DocumentsModule | None:
    effective_blob_storage: BlobStoragePort

    if blob_storage is not None:
        effective_blob_storage = blob_storage
    else:
        if not settings.azure_blob_enabled:
            return None

        connection_string = settings.azure_blob_connection_string
        if connection_string is None:
            raise RuntimeError(
                "azure_blob_connection_string is required when "
                "azure_blob_enabled is true"
            )

        effective_blob_storage = AzureBlobStorage(
            connection_string=connection_string.get_secret_value(),
            container_name=settings.azure_blob_container_name,
        )

    def unit_of_work_factory() -> DocumentsUnitOfWork:
        return DocumentsUnitOfWork(session_factory)

    resources: list[ManagedResource] = []

    if isinstance(effective_blob_storage, ManagedResource):
        resources.append(effective_blob_storage)

    if settings.outbox_publisher_enabled:
        effective_publisher = publisher

        if effective_publisher is None:
            effective_publisher = ConfluentKafkaPublisher(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                client_id=settings.kafka_client_id,
            )

        outbox_publisher = OutboxPublisher(
            session_factory=session_factory,
            publisher=effective_publisher,
            batch_size=settings.outbox_publish_batch_size,
            poll_interval_seconds=settings.outbox_poll_interval_seconds,
            max_retries=settings.outbox_max_retries,
        )
        resources.append(outbox_publisher)

    if settings.document_ingestion_enabled:
        if not isinstance(effective_blob_storage, BlobDownloaderPort):
            raise RuntimeError("document_ingestion_enabled requires blob download support")
        resources.append(
            DocumentIngestionConsumer(
                session_factory=session_factory,
                blob_downloader=effective_blob_storage,
                memory_store=MemoryRecordRepository(
                    session_factory=session_factory,
                    embedding_model=settings.embedding_model,
                    user_memory_namespace=settings.pinecone_user_memory_namespace,
                    documents_namespace=settings.pinecone_documents_namespace,
                ),
                text_extractor=TextExtractor(),
                chunker=TokenChunker(
                    chunk_tokens=settings.document_chunk_tokens,
                    overlap_tokens=settings.document_chunk_overlap_tokens,
                ),
                batch_size=settings.document_ingestion_batch_size,
                poll_interval_seconds=settings.document_ingestion_poll_interval_seconds,
                topic_name=settings.kafka_documents_topic,
            )
        )

    return DocumentsModule(
        unit_of_work_factory=unit_of_work_factory,
        upload_document=UploadDocument(
            unit_of_work_factory=unit_of_work_factory,
            blob_storage=effective_blob_storage,
            topic_name=settings.kafka_documents_topic,
        ),
        upload_policy=DocumentUploadPolicy(
            max_bytes=settings.documents_upload_max_bytes,
            allowed_content_types=frozenset(
                settings.documents_allowed_content_types
            ),
        ),
        resources=tuple(resources),
    )
