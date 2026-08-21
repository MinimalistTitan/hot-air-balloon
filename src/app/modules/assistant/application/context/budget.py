from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.assistant.domain.context import ContextBlock, ContextKind


@dataclass(slots=True)
class TokenBudgetAllocator:
    kind_shares: dict[ContextKind, int] = field(
        default_factory=lambda: {
            ContextKind.SYSTEM_DIRECTIVE: 10,
            ContextKind.CONVERSATION_SUMMARY: 25,
            ContextKind.RECENT_TURN: 35,
            ContextKind.RETRIEVED_DOCUMENT: 20,
            ContextKind.USER_MEMORY: 10,
            ContextKind.TOOL_RESULT: 10,
        }
    )

    def allocate(
        self,
        blocks: list[ContextBlock],
        *,
        total_budget: int,
        counter: object,
    ) -> tuple[list[ContextBlock], int]:
        del counter
        ordered = sorted(
            blocks,
            key=lambda block: (
                self.kind_shares.get(block.kind, 0),
                block.source,
                block.content,
            ),
            reverse=True,
        )
        selected: list[ContextBlock] = []
        used_tokens = 0
        dropped = 0

        for block in ordered:
            token_count = max(block.token_count, 0)
            if token_count == 0:
                token_count = max(len(block.content.split()), 1)
            if used_tokens + token_count <= total_budget:
                selected.append(block)
                used_tokens += token_count
                continue
            dropped += 1

        return selected, dropped
