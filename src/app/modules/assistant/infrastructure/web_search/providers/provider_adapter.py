from abc import ABC, abstractmethod

from app.modules.assistant.domain.ports.web_search import (
    WebSearchQuery,
    WebSearchResult,
)


class ProviderWebSearchAdapter(ABC):
    @abstractmethod
    async def search(self, query: WebSearchQuery) -> list[WebSearchResult]:
        """Execute a search with the provider's API."""
