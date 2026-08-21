from __future__ import annotations

from dataclasses import dataclass

from app.modules.assistant.application.context.providers import ContextProviderPort, ContextRequest
from app.modules.assistant.application.ports import TokenCounterPort
from app.modules.assistant.domain.context import ContextBlock, ContextKind


@dataclass(slots=True)
class RecentTurnsProvider(ContextProviderPort):
    counter: TokenCounterPort

    async def get_blocks(self, request: ContextRequest) -> list[ContextBlock]:
        return [
            ContextBlock(
                kind=ContextKind.RECENT_TURN,
                content=f"{turn.role}: {turn.content}",
                source="recent_turns",
                token_count=self.counter.count(f"{turn.role}: {turn.content}"),
            )
            for turn in request.recent_turns
        ]
