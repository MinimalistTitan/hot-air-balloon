from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver

from app.core.config import Settings
from app.core.database.database import SessionFactory
from app.modules.assistant.application.context.assembler import DefaultContextAssembler
from app.modules.assistant.application.context.budget import TokenBudgetAllocator
from app.modules.assistant.application.context.document_recall_provider import (
    DocumentRecallProvider,
)
from app.modules.assistant.application.context.providers import ContextProviderPort
from app.modules.assistant.application.context.recent_turns_provider import RecentTurnsProvider
from app.modules.assistant.application.context.user_memory_provider import UserMemoryProvider
from app.modules.assistant.application.ports import (
    AgentOrchestratorPort,
    AssistantTelemetryPort,
    ContextAssemblerPort,
    ConversationStorePort,
    ToolRuntimePort,
    UserMemoryErasePort,
)
from app.modules.assistant.application.use_cases import (
    EraseUserMemory,
    OrchestrateAssistantQuery,
)
from app.modules.assistant.domain.ports.web_search import WebSearchPort
from app.modules.assistant.domain.tool_call import ToolCallPolicy
from app.modules.assistant.infrastructure.agents.langgraph.agent_brain import (
    AgentBrain,
)
from app.modules.assistant.infrastructure.agents.langgraph.checkpoint_eraser import (
    LangGraphCheckpointEraser,
)
from app.modules.assistant.infrastructure.agents.langgraph.context import DecisionObserver
from app.modules.assistant.infrastructure.agents.langgraph.orchestrator import (
    LangGraphAgentOrchestrator,
)
from app.modules.assistant.infrastructure.agents.langgraph.postgres_checkpointer import (
    PostgresCheckpointer,
)
from app.modules.assistant.infrastructure.context.tiktoken_counter import TiktokenCounter
from app.modules.assistant.infrastructure.conversation_memory.in_memory.inmemory_conversation_store import (
    InMemoryConversationStore,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.document_memory_reader import (
    PineconeDocumentMemoryReader,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.memory_record_repository import (
    MemoryRecordRepository,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.openai_embedding_client import (
    OpenAIEmbeddingClient,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.pinecone_index import (
    PineconeVectorIndex,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.rederivable_fields import (
    collect_rederivable_fields,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.user_memory_eraser import (
    UserMemoryEraser,
)
from app.modules.assistant.infrastructure.conversation_memory.short_term.postgres_conversation_store import (
    ConversationStore,
)
from app.modules.assistant.infrastructure.llm.langchain_llm_client import (
    LangChainChatModelFactory,
)
from app.modules.assistant.infrastructure.telemetry.orchestration_observability import (
    StructlogAssistantTelemetry,
)
from app.modules.assistant.infrastructure.tool_runtime.gateway_runtime import GatewayToolRuntime
from app.modules.assistant.infrastructure.web_search.tool import build_web_search_tool
from app.modules.assistant.tool_gateway.domain import AssistantToolRegistration
from app.modules.assistant.tool_gateway.registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class AssistantModule:
    query: OrchestrateAssistantQuery
    erase_user_memory: EraseUserMemory | None = None
    rederivable_terms: frozenset[str] = frozenset()


def build_langgraph_agent_orchestrator(
    settings: Settings,
    *,
    checkpointer: BaseCheckpointSaver[Any] | PostgresCheckpointer | None = None,
    decision_observer: DecisionObserver | None = None,
) -> LangGraphAgentOrchestrator | None:
    if settings.chat_api_key is None:
        return None

    llm = LangChainChatModelFactory(settings).build()
    return LangGraphAgentOrchestrator(
        brain=AgentBrain(llm=llm),
        model_name=llm.model_name,
        checkpointer=checkpointer,
        decision_observer=decision_observer,
    )


def build_assistant_module(
    settings: Settings,
    tools: Iterable[AssistantToolRegistration],
    *,
    session_factory: SessionFactory | None = None,
    web_search_provider: WebSearchPort | None = None,
    tool_runtime: ToolRuntimePort | None = None,
    agent_orchestrator: AgentOrchestratorPort | None = None,
    conversation_store: ConversationStorePort | None = None,
    telemetry: AssistantTelemetryPort | None = None,
    tool_policy: ToolCallPolicy | None = None,
    context_assembler: ContextAssemblerPort | None = None,
    user_memory_eraser: UserMemoryErasePort | None = None,
    checkpointer: BaseCheckpointSaver[Any] | PostgresCheckpointer | None = None,
) -> AssistantModule | None:
    registered_tools = list(tools)
    if web_search_provider is not None:
        registered_tools.append(build_web_search_tool(web_search_provider))

    registered_tools_tuple = tuple(registered_tools)

    effective_telemetry = telemetry if telemetry is not None else StructlogAssistantTelemetry()

    effective_orchestrator = agent_orchestrator

    if effective_orchestrator is None:
        effective_orchestrator = build_langgraph_agent_orchestrator(
            settings=settings,
            checkpointer=checkpointer,
            decision_observer=effective_telemetry.decision_recorded,
        )

    if effective_orchestrator is None:
        return None

    effective_policy = tool_policy
    if effective_policy is None:
        effective_policy = ToolCallPolicy(
            allowed_tool_names=frozenset(tool.definition.name for tool in registered_tools_tuple),
            max_total_calls=1,
            max_calls_per_tool=1,
            fail_on_policy_violation=True,
        )

    registry = ToolRegistry()
    for tool in registered_tools_tuple:
        registry.register(tool)
    rederivable_terms = collect_rederivable_fields(registry).terms

    effective_tool_runtime = tool_runtime
    if effective_tool_runtime is None:
        if session_factory is None:
            raise ValueError("session_factory is required when tool_runtime is not provided")

        effective_tool_runtime = GatewayToolRuntime(
            registry=registry,
            session_factory=session_factory,
        )

    effective_conversation_store = (
        conversation_store
        if conversation_store is not None
        else (
            ConversationStore(
                session_factory=session_factory,
                retention_days=settings.short_term_retention_days,
            )
            if session_factory is not None
            else InMemoryConversationStore(max_turns_per_conversation=12)
        )
    )

    effective_context_assembler = context_assembler
    if effective_context_assembler is None:
        counter = TiktokenCounter()
        providers: list[ContextProviderPort] = [RecentTurnsProvider(counter=counter)]
        if settings.long_term_memory_enabled and session_factory is not None:
            memory_repository = MemoryRecordRepository(
                session_factory=session_factory,
                embedding_model=settings.embedding_model,
                user_memory_namespace=settings.pinecone_user_memory_namespace,
                documents_namespace=settings.pinecone_documents_namespace,
            )
            providers.append(
                UserMemoryProvider(
                    memory_reader=memory_repository,
                    counter=counter,
                    limit=settings.long_term_recall_top_k,
                )
            )
            if settings.pinecone_api_key is not None and settings.embedding_api_key is not None:
                providers.append(
                    DocumentRecallProvider(
                        memory_reader=PineconeDocumentMemoryReader(
                            embedding_client=OpenAIEmbeddingClient(
                                api_key=settings.embedding_api_key.get_secret_value(),
                                model=settings.embedding_model,
                                base_url=settings.chat_base_url,
                            ),
                            vector_index=PineconeVectorIndex(
                                api_key=settings.pinecone_api_key.get_secret_value(),
                                index_name=settings.pinecone_index_name,
                            ),
                            memory_repository=memory_repository,
                            namespace=settings.pinecone_documents_namespace,
                        ),
                        counter=counter,
                        limit=settings.long_term_recall_top_k,
                    )
                )
        effective_context_assembler = DefaultContextAssembler(
            providers=tuple(providers),
            allocator=TokenBudgetAllocator(),
            token_counter=counter,
            total_budget=settings.context_budget_tokens,
        )

    effective_user_memory_eraser = user_memory_eraser
    if (
        effective_user_memory_eraser is None
        and settings.long_term_memory_enabled
        and session_factory is not None
        and settings.pinecone_api_key is not None
    ):
        effective_user_memory_eraser = UserMemoryEraser(
            session_factory=session_factory,
            vector_index=PineconeVectorIndex(
                api_key=settings.pinecone_api_key.get_secret_value(),
                index_name=settings.pinecone_index_name,
            ),
            checkpoint_eraser=(
                LangGraphCheckpointEraser(checkpointer) if checkpointer is not None else None
            ),
        )

    return AssistantModule(
        query=OrchestrateAssistantQuery(
            tool_runtime=effective_tool_runtime,
            agent_orchestrator=effective_orchestrator,
            conversation_store=effective_conversation_store,
            telemetry=effective_telemetry,
            tool_policy=effective_policy,
            context_assembler=effective_context_assembler,
        ),
        erase_user_memory=(
            EraseUserMemory(effective_user_memory_eraser)
            if effective_user_memory_eraser is not None
            else None
        ),
        rederivable_terms=rederivable_terms,
    )
