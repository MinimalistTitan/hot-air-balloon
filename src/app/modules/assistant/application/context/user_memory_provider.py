from __future__ import annotations

from dataclasses import dataclass

from app.modules.assistant.application.context.providers import ContextProviderPort, ContextRequest
from app.modules.assistant.application.ports import TokenCounterPort, UserMemoryReaderPort
from app.modules.assistant.domain.context import ContextBlock, ContextKind


@dataclass(slots=True)
class UserMemoryProvider(ContextProviderPort):
    memory_reader: UserMemoryReaderPort
    counter: TokenCounterPort
    limit: int

    async def get_blocks(self, request: ContextRequest) -> list[ContextBlock]:
        memories = await self.memory_reader.read_recent_user_memories(
            owner_user_id=request.authorization_context.user_id,
            limit=self.limit,
        )
        return [
            ContextBlock(
                kind=ContextKind.USER_MEMORY,
                content=memory,
                source="user_memory",
                token_count=self.counter.count(memory),
            )
            for memory in memories
        ]
