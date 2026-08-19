from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class WebSearchQuery:
    query: str
    max_results: int
    language: str | None
    safe_search: bool


@dataclass(frozen=True, slots=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str
    published_at: str | None = None


class WebSearchPort(Protocol):
    async def search(self, query: WebSearchQuery) -> list[WebSearchResult]: ...
