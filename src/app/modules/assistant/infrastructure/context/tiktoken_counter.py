from __future__ import annotations

from dataclasses import dataclass

import tiktoken

from app.modules.assistant.application.ports import TokenCounterPort


@dataclass(slots=True)
class TiktokenCounter(TokenCounterPort):
    model: str = "gpt-4o-mini"

    def count(self, text: str) -> int:
        if not text:
            return 0
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
