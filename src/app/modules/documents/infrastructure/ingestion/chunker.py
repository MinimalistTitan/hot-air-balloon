from dataclasses import dataclass

import tiktoken


@dataclass(frozen=True, slots=True)
class TokenChunker:
    chunk_tokens: int
    overlap_tokens: int
    encoding_name: str = "cl100k_base"

    def chunk(self, text: str) -> list[str]:
        tokens = tiktoken.get_encoding(self.encoding_name).encode(text)
        if not tokens:
            return []
        encoding = tiktoken.get_encoding(self.encoding_name)
        step = self.chunk_tokens - self.overlap_tokens
        return [
            encoding.decode(tokens[start : start + self.chunk_tokens]).strip()
            for start in range(0, len(tokens), step)
            if encoding.decode(tokens[start : start + self.chunk_tokens]).strip()
        ]
