from pydantic import BaseModel, ConfigDict, Field

from app.modules.assistant.domain.ports.web_search import WebSearchPort, WebSearchQuery
from app.modules.assistant.infrastructure.web_search.web_search_service import (
    WebSearchService,
)
from app.modules.assistant.tool_gateway.domain import ToolDefinition, ToolRateLimit
from app.modules.user.domain.authorization import Permission


class WebSearchToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=10)
    language: str | None = Field(default=None, min_length=2, max_length=10)
    safe_search: bool = True


class WebSearchToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    snippet: str
    published_at: str | None = None


class WebSearchToolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = "web_search"
    results: list[WebSearchToolResult]


def build_web_search_tool(provider: WebSearchPort) -> ToolDefinition:
    service = WebSearchService(provider=provider)

    async def invoke(payload: dict[str, object]) -> dict[str, object]:
        data = WebSearchToolInput.model_validate(payload)
        results = await service.search(
            WebSearchQuery(
                query=data.query,
                max_results=data.max_results,
                language=data.language,
                safe_search=data.safe_search,
            )
        )
        output = WebSearchToolOutput(
            results=[
                WebSearchToolResult(
                    title=result.title,
                    url=result.url,
                    snippet=result.snippet,
                    published_at=result.published_at,
                )
                for result in results
            ]
        )
        return output.model_dump(mode="json")

    return ToolDefinition(
        name="web_search",
        description="Search public web sources for current information",
        input_model=WebSearchToolInput,
        output_model=WebSearchToolOutput,
        handler=invoke,
        required_permission=Permission.WEB_SEARCH,
        rate_limit=ToolRateLimit(max_calls=5, window_seconds=60),
    )
