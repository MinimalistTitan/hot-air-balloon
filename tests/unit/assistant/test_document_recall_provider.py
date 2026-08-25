from uuid import uuid4

from app.modules.assistant.application.context.document_recall_provider import (
    DocumentRecallProvider,
)
from app.modules.assistant.application.context.providers import ContextRequest
from app.modules.assistant.infrastructure.context.tiktoken_counter import TiktokenCounter
from app.modules.user.domain.authorization import AuthorizationContext, RoleName


class FakeDocumentMemoryReader:
    async def read_document_chunks(
        self,
        query: str,
        authorization_context: AuthorizationContext,
        limit: int,
    ) -> list[str]:
        del query, authorization_context, limit
        return ["Scheduled maintenance procedures for Pump A."]


async def test_document_recall_requires_documents_permission() -> None:
    provider = DocumentRecallProvider(
        memory_reader=FakeDocumentMemoryReader(),
        counter=TiktokenCounter(),
        limit=3,
    )
    request = ContextRequest(
        conversation_id=uuid4(),
        user_query="How do I maintain Pump A?",
        authorization_context=AuthorizationContext(
            user_id=uuid4(),
            roles=frozenset({RoleName.READ_ONLY_ANALYST}),
        ),
    )

    blocks = await provider.get_blocks(request)

    assert len(blocks) == 1
    assert blocks[0].source == "document_recall"
