from uuid import UUID

from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.core.database.database import create_session_factory
from app.modules.assistant.application.ports import ConversationTurn, ToolInvoker
from app.modules.assistant.domain.entities import AgentRunResult, ToolDescriptor
from app.modules.assistant.domain.ports.web_search import (
    WebSearchPort,
    WebSearchQuery,
    WebSearchResult,
)
from app.modules.assistant.domain.tool_call import ToolCallPolicy
from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from app.modules.assistant.wiring import build_assistant_module, build_langgraph_agent_orchestrator
from app.modules.operations.wiring import build_operations_module
from app.modules.user.contracts.consistency_auditor import TOOL_USERS_CONSISTENCY_AUDITOR_V1
from app.modules.user.wiring import build_users_module


class FakeWebSearchProvider(WebSearchPort):
    async def search(self, query: WebSearchQuery) -> list[WebSearchResult]:
        return []


class FakeAgentOrchestrator:
    async def run(
        self,
        conversation_id: UUID,
        user_query: str,
        available_tools: list[ToolDescriptor],
        tool_invoker: ToolInvoker,
        conversation_history: list[ConversationTurn],
        tool_policy: ToolCallPolicy,
        max_tool_calls: int,
        allow_tool_calls: bool,
    ) -> AgentRunResult:
        return AgentRunResult(
            answer="unused",
            agent_name="test",
            model_name="test",
            finish_reason=OrchestrationFinishReason.COMPLETED,
            tool_calls=[],
        )


async def test_build_langgraph_agent_orchestrator_passes_checkpointer() -> None:
    settings = Settings(database_url="sqlite+aiosqlite://", chat_api_key="test-key")
    checkpointer = InMemorySaver()

    orchestrator = build_langgraph_agent_orchestrator(
        settings=settings,
        checkpointer=checkpointer,
    )

    assert orchestrator is not None
    assert orchestrator.checkpointer is checkpointer


async def test_assistant_wiring_composes_all_gateway_tools() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = create_session_factory(engine)
    settings = Settings(database_url="sqlite+aiosqlite://")
    users = build_users_module(settings, session_factory)
    operations = build_operations_module(settings, session_factory)

    module = build_assistant_module(
        settings,
        tools=(*users.tools, *operations.tools, *operations.write_tools),
        session_factory=session_factory,
        web_search_provider=FakeWebSearchProvider(),
        agent_orchestrator=FakeAgentOrchestrator(),
    )

    assert module is not None
    tools = await module.query.tool_runtime.list_tools()

    assert {tool.name for tool in tools} == {
        TOOL_USERS_CONSISTENCY_AUDITOR_V1,
        "get_asset_status",
        "get_maintenance_tickets",
        "get_production_schedule",
        "get_spare_parts_availability",
        "get_work_orders",
        "web_search",
        "write_work_order_status",
    }

    await engine.dispose()
