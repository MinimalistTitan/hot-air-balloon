from __future__ import annotations

from dataclasses import dataclass

from app.modules.assistant.application.context.providers import ContextProviderPort, ContextRequest
from app.modules.assistant.application.ports import TokenCounterPort
from app.modules.assistant.domain.context import ContextBlock, ContextKind


@dataclass(slots=True)
class ConversationEvidenceProvider(ContextProviderPort):
    counter: TokenCounterPort

    async def get_blocks(self, request: ContextRequest) -> list[ContextBlock]:
        """Get context blocks from recent conversation evidence.
           And use them to create context blocks for the assistant.
           which can then be used by the assistant to provide more informed responses.
        Args:
            request (ContextRequest): The context request containing recent conversation evidence.

        Returns:
            list[ContextBlock]: A list of context blocks created from the recent conversation evidence.
        """
        blocks: list[ContextBlock] = []
        for snapshot in request.recent_evidence:
            content = snapshot.to_context_text()
            blocks.append(
                ContextBlock(
                    kind=ContextKind.TOOL_RESULT,
                    content=content,
                    source="conversation_evidence",
                    token_count=self.counter.count(content),
                )
            )
        return blocks
