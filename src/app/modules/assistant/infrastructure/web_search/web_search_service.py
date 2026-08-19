from dataclasses import dataclass

from app.modules.assistant.domain.ports.web_search import (
    WebSearchPort,
    WebSearchQuery,
    WebSearchResult,
)


@dataclass(frozen=True, slots=True)
class WebSearchService:
    provider: WebSearchPort

    async def search(self, query: WebSearchQuery) -> list[WebSearchResult]:
        return await self.provider.search(query)
