from dataclasses import dataclass

from app.modules.assistant.application.ports import (
    DocumentMemoryReaderPort,
    EmbeddingPort,
    VectorIndexPort,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.memory_record_repository import (
    MemoryRecordRepository,
)
from app.modules.user.domain.authorization import AuthorizationContext, Permission


@dataclass(slots=True)
class PineconeDocumentMemoryReader(DocumentMemoryReaderPort):
    embedding_client: EmbeddingPort
    vector_index: VectorIndexPort
    memory_repository: MemoryRecordRepository
    namespace: str

    async def read_document_chunks(
        self,
        query: str,
        authorization_context: AuthorizationContext,
        limit: int,
    ) -> list[str]:
        if limit <= 0 or not authorization_context.can(Permission.DOCUMENTS_READ):
            return []

        vector = await self.embedding_client.embed(query)
        vector_ids = await self.vector_index.query_ids(
            namespace=self.namespace,
            values=vector,
            limit=limit,
            metadata_filter={"kind": "document_chunk"},
        )
        return await self.memory_repository.read_document_chunks_by_vector_ids(
            vector_ids=vector_ids,
            authorization_context=authorization_context,
        )
