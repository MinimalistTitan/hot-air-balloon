from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.modules.assistant.application.context.budget import TokenBudgetAllocator
from app.modules.assistant.application.context.providers import ContextProviderPort, ContextRequest
from app.modules.assistant.application.ports import TokenCounterPort
from app.modules.assistant.domain.context import AssembledContext, ContextBlock


@dataclass(slots=True)
class DefaultContextAssembler:
    providers: tuple[ContextProviderPort, ...]
    allocator: TokenBudgetAllocator
    token_counter: TokenCounterPort
    total_budget: int = 8000

    async def assemble(self, request: ContextRequest) -> AssembledContext:
        aggregated: list[ContextBlock] = []
        tasks = [provider.get_blocks(request) for provider in self.providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                continue
            aggregated.extend(result)

        normalized = [
            ContextBlock(
                kind=block.kind,
                content=block.content,
                source=block.source,
                token_count=block.token_count or self.token_counter.count(block.content),
            )
            for block in aggregated
        ]

        selected, dropped = self.allocator.allocate(
            normalized,
            total_budget=self.total_budget,
            counter=self.token_counter,
        )
        total_tokens = sum(block.token_count for block in selected)
        return AssembledContext(
            blocks=selected,
            total_tokens=total_tokens,
            dropped_block_count=dropped,
        )
