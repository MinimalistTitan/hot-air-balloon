from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver

from app.core.config import Settings
from app.core.database.database import SessionFactory
from app.modules.assistant.application.ports import (
    AgentOrchestratorPort,
    AssistantTelemetryPort,
    ConversationStorePort,
    ToolRuntimePort,
)
from app.modules.assistant.application.use_cases import (
    OrchestrateAssistantQuery,
)
from app.modules.assistant.domain.ports.web_search import WebSearchPort
from app.modules.assistant.domain.tool_call import ToolCallPolicy
from app.modules.assistant.infrastructure.agents.langgraph.agent_brain import (
    AgentBrain,
)
from app.modules.assistant.infrastructure.agents.langgraph.orchestrator import (
    LangGraphAgentOrchestrator,
)
from app.modules.assistant.infrastructure.conversation_memory.inmemory_conversation_store import (
    InMemoryConversationStore,
)
from app.modules.assistant.infrastructure.llm.langchain_llm_client import (
    LangChainChatModelFactory,
)
from app.modules.assistant.infrastructure.telemetry.orchestration_observability import (
    StructlogAssistantTelemetry,
)
from app.modules.assistant.infrastructure.tool_runtime.gateway_runtime import GatewayToolRuntime
from app.modules.assistant.infrastructure.web_search.tool import build_web_search_tool
from app.modules.assistant.tool_gateway.domain import ToolDefinition
from app.modules.assistant.tool_gateway.registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class AssistantModule:
    query: OrchestrateAssistantQuery


def build_langgraph_agent_orchestrator(
    settings: Settings,
    *,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> LangGraphAgentOrchestrator | None:
    if settings.chat_api_key is None:
        return None

    llm = LangChainChatModelFactory(settings).build()
    return LangGraphAgentOrchestrator(
        brain=AgentBrain(llm=llm),
        model_name=llm.model_name,
        checkpointer=checkpointer,
    )


def build_assistant_module(
    settings: Settings,
    tools: Iterable[ToolDefinition],
    *,
    session_factory: SessionFactory | None = None,
    web_search_provider: WebSearchPort | None = None,
    tool_runtime: ToolRuntimePort | None = None,
    agent_orchestrator: AgentOrchestratorPort | None = None,
    conversation_store: ConversationStorePort | None = None,
    telemetry: AssistantTelemetryPort | None = None,
    tool_policy: ToolCallPolicy | None = None,
) -> AssistantModule | None:
    registered_tools = list(tools)
    if web_search_provider is not None:
        registered_tools.append(build_web_search_tool(web_search_provider))

    registered_tools_tuple = tuple(registered_tools)

    effective_orchestrator = agent_orchestrator
    
    if effective_orchestrator is None:
        effective_orchestrator = build_langgraph_agent_orchestrator(settings=settings)

    if effective_orchestrator is None:
        return None

    effective_policy = tool_policy
    if effective_policy is None:
        effective_policy = ToolCallPolicy(
            allowed_tool_names=frozenset(
                tool.name for tool in registered_tools_tuple
            ),
            max_total_calls=1,
            max_calls_per_tool=1,
            fail_on_policy_violation=True,
        )

    effective_tool_runtime = tool_runtime
    if effective_tool_runtime is None:
        if session_factory is None:
            raise ValueError("session_factory is required when tool_runtime is not provided")

        registry = ToolRegistry()

        for tool in registered_tools_tuple:
            registry.register(tool)

        effective_tool_runtime = GatewayToolRuntime(
            registry=registry,
            session_factory=session_factory,
        )

    effective_conversation_store = (
        conversation_store
        if conversation_store is not None
        else InMemoryConversationStore(
            max_turns_per_conversation=12
        )
    )

    effective_telemetry = (
        telemetry
        if telemetry is not None
        else StructlogAssistantTelemetry()
    )

    return AssistantModule(
        query=OrchestrateAssistantQuery(
            tool_runtime=effective_tool_runtime,
            agent_orchestrator=effective_orchestrator,
            conversation_store=effective_conversation_store,
            telemetry=effective_telemetry,
            tool_policy=effective_policy,
        )
    )