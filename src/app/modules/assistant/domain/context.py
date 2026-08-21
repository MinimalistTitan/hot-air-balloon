from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ContextKind(StrEnum):
    SYSTEM_DIRECTIVE = "system_directive"
    CONVERSATION_SUMMARY = "conversation_summary"
    RECENT_TURN = "recent_turn"
    RETRIEVED_DOCUMENT = "retrieved_document"
    USER_MEMORY = "user_memory"
    TOOL_RESULT = "tool_result"


@dataclass(frozen=True, slots=True)
class ContextBlock:
    kind: ContextKind
    content: str
    source: str
    token_count: int = 0

    def render(self) -> str:
        title = self.kind.value.replace("_", " ").title()
        return f"[{title}] {self.content}"


@dataclass(frozen=True, slots=True)
class AssembledContext:
    blocks: list[ContextBlock] = field(default_factory=list)
    total_tokens: int = 0
    dropped_block_count: int = 0

    def render(self) -> str:
        if not self.blocks:
            return ""
        return "\n\n".join(block.render() for block in self.blocks)
