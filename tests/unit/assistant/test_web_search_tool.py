import pytest
from pydantic import ValidationError

from app.modules.assistant.domain.ports.web_search import (
    WebSearchQuery,
    WebSearchResult,
)
from app.modules.assistant.infrastructure.web_search.tool import build_web_search_tool


class FakeWebSearchProvider:
    def __init__(self) -> None:
        self.query: WebSearchQuery | None = None

    async def search(self, query: WebSearchQuery) -> list[WebSearchResult]:
        self.query = query
        return [
            WebSearchResult(
                title="Example result",
                url="https://example.com/result",
                snippet="A relevant result.",
                published_at="2026-08-17T00:00:00Z",
            )
        ]


async def test_web_search_tool_delegates_to_provider_with_typed_query() -> None:
    provider = FakeWebSearchProvider()
    tool = build_web_search_tool(provider)

    result = await tool.handler(
        {
            "query": "latest production schedule",
            "max_results": 3,
            "language": "en",
            "safe_search": True,
        }
    )

    assert provider.query == WebSearchQuery(
        query="latest production schedule",
        max_results=3,
        language="en",
        safe_search=True,
    )
    assert result == {
        "tool_name": "web_search",
        "results": [
            {
                "title": "Example result",
                "url": "https://example.com/result",
                "snippet": "A relevant result.",
                "published_at": "2026-08-17T00:00:00Z",
            }
        ],
    }


async def test_web_search_tool_rejects_invalid_requests() -> None:
    tool = build_web_search_tool(FakeWebSearchProvider())

    with pytest.raises(ValidationError):
        await tool.handler({"query": "", "max_results": 11})
