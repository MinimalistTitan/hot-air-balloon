from __future__ import annotations

from dataclasses import dataclass

from app.modules.assistant.application.context.providers import ContextProviderPort, ContextRequest
from app.modules.assistant.application.ports import DocumentMemoryReaderPort, TokenCounterPort
from app.modules.assistant.domain.context import ContextBlock, ContextKind
from app.modules.user.domain.authorization import Permission


@dataclass(slots=True)
class DocumentRecallProvider(ContextProviderPort):
    memory_reader: DocumentMemoryReaderPort
    counter: TokenCounterPort
    limit: int

    async def get_blocks(self, request: ContextRequest) -> list[ContextBlock]:
        if not request.authorization_context.can(Permission.DOCUMENTS_READ):
            return []

        chunks = await self.memory_reader.read_document_chunks(
            query=request.user_query,
            authorization_context=request.authorization_context,
            limit=self.limit,
        )
        return [
            ContextBlock(
                kind=ContextKind.RETRIEVED_DOCUMENT,
                content=chunk,
                source="document_recall",
                token_count=self.counter.count(chunk),
            )
            for chunk in chunks
        ]
