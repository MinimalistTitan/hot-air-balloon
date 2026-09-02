from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Self, cast

from fastapi import Request
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.database.database import SessionFactory, create_engine, create_session_factory
from app.core.life_cycle import ManagedResource
from app.modules.assistant.application.facts.act_policy import FactAcceptancePolicy
from app.modules.assistant.application.ports import (
    AgentOrchestratorPort,
    AssistantTelemetryPort,
    ConversationStorePort,
    ToolRuntimePort,
)
from app.modules.assistant.domain.ports.web_search import WebSearchPort
from app.modules.assistant.domain.tool_call import ToolCallPolicy
from app.modules.assistant.infrastructure.agents.langgraph.checkpoint_eraser import (
    LangGraphCheckpointEraser,
)
from app.modules.assistant.infrastructure.agents.langgraph.postgres_checkpointer import (
    PostgresCheckpointer,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.candidate_repository import (
    FactCandidateRepository,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.consolidation_worker import (
    ConsolidationWorker,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.fact_extractor import (
    LlmFactExtractor,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.fact_promoter import (
    FactPromoter,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.memory_record_repository import (
    MemoryRecordRepository,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.memory_retention_job import (
    MemoryRetentionJob,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.openai_embedding_client import (
    OpenAIEmbeddingClient,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.pinecone_index import (
    PineconeVectorIndex,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.reconciliation_job import (
    ReconciliationJob,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.vector_sync_worker import (
    VectorSyncWorker,
)
from app.modules.assistant.infrastructure.conversation_memory.short_term.short_term_retention_job import (
    ShortTermRetentionJob,
)
from app.modules.assistant.infrastructure.llm.langchain_llm_client import LangChainChatModelFactory
from app.modules.assistant.wiring import AssistantModule, build_assistant_module
from app.modules.documents.application.ports import BlobStoragePort
from app.modules.documents.wiring import DocumentsModule, build_documents_module
from app.modules.operations.wiring import OperationsModule, build_operations_module
from app.modules.user.wiring import UsersModule, build_users_module
from app.shared.messaging.kafka.kafka_callout import MessagePublisher


@dataclass(slots=True)
class Container:
    settings: Settings
    engine: AsyncEngine
    session_factory: SessionFactory
    users: UsersModule
    assistant: AssistantModule | None
    # langchain_smoke_check: LangChainSmokeCheck | None
    documents: DocumentsModule | None
    operations: OperationsModule | None

    _resources: tuple[ManagedResource, ...] = field(
        default_factory=tuple,
        repr=False,
    )
    _started_resources: list[ManagedResource] = field(
        default_factory=list,
        init=False,
        repr=False,
    )
    _started: bool = field(
        default=False,
        init=False,
        repr=False,
    )
    _closed: bool = field(
        default=False,
        init=False,
        repr=False,
    )

    @classmethod
    def build(
        cls,
        settings: Settings,
        engine: AsyncEngine | None = None,
        *,
        blob_storage: BlobStoragePort | None = None,
        publisher: MessagePublisher | None = None,
        web_search_provider: WebSearchPort | None = None,
        assistant_tool_runtime: ToolRuntimePort | None = None,
        assistant_agent_orchestrator: AgentOrchestratorPort | None = None,
        assistant_conversation_store: ConversationStorePort | None = None,
        assistant_telemetry: AssistantTelemetryPort | None = None,
        assistant_tool_policy: ToolCallPolicy | None = None,
        assistant_checkpointer: BaseCheckpointSaver[Any] | PostgresCheckpointer | None = None,
        managed_resources: Iterable[ManagedResource] = (),
    ) -> Self:
        database_engine = engine if engine is not None else create_engine(settings)
        session_factory = create_session_factory(database_engine)

        users = build_users_module(
            settings=settings,
            session_factory=session_factory,
        )

        documents = build_documents_module(
            settings=settings,
            session_factory=session_factory,
            blob_storage=blob_storage,
            publisher=publisher,
        )

        operations = build_operations_module(
            settings=settings,
            session_factory=session_factory,
        )

        assistant_tools = (*users.tools, *operations.tools)
        effective_assistant_checkpointer = assistant_checkpointer

        if effective_assistant_checkpointer is None and settings.assistant_checkpointing_enabled:
            effective_assistant_checkpointer = PostgresCheckpointer(settings.database_url)

        assistant = build_assistant_module(
            settings=settings,
            tools=assistant_tools,
            session_factory=session_factory,
            web_search_provider=web_search_provider,
            tool_runtime=assistant_tool_runtime,
            agent_orchestrator=assistant_agent_orchestrator,
            conversation_store=assistant_conversation_store,
            telemetry=assistant_telemetry,
            tool_policy=assistant_tool_policy,
            checkpointer=effective_assistant_checkpointer,
        )

        resources = list(managed_resources)

        def append_resource_once(resource: ManagedResource) -> None:
            if any(existing is resource for existing in resources):
                return
            resources.append(resource)

        if assistant is not None and isinstance(effective_assistant_checkpointer, ManagedResource):
            append_resource_once(effective_assistant_checkpointer)
        if assistant is not None and isinstance(
            assistant.query.agent_orchestrator, ManagedResource
        ):
            append_resource_once(assistant.query.agent_orchestrator)

        resources.append(
            ShortTermRetentionJob(
                session_factory=session_factory,
                retention_days=settings.short_term_retention_days,
                assistant_conversation_retention_days=settings.assistant_conversation_retention_days,
                purge_interval_seconds=settings.short_term_retention_interval_seconds,
                checkpoint_eraser=(
                    LangGraphCheckpointEraser(effective_assistant_checkpointer)
                    if effective_assistant_checkpointer is not None
                    else None
                ),
            )
        )
        if settings.long_term_memory_enabled:
            pinecone_api_key = settings.pinecone_api_key
            embedding_api_key = settings.embedding_api_key
            if pinecone_api_key is None or embedding_api_key is None:
                raise RuntimeError("Long-term memory credentials were not validated")
            vector_index = PineconeVectorIndex(
                api_key=pinecone_api_key.get_secret_value(),
                index_name=settings.pinecone_index_name,
            )
            resources.append(
                VectorSyncWorker(
                    session_factory=session_factory,
                    embedding_client=OpenAIEmbeddingClient(
                        api_key=embedding_api_key.get_secret_value(),
                        model=settings.embedding_model,
                        base_url=settings.chat_base_url,
                    ),
                    vector_index=vector_index,
                    batch_size=settings.vector_sync_batch_size,
                    poll_interval_seconds=settings.vector_sync_poll_interval_seconds,
                )
            )
            resources.append(
                ReconciliationJob(
                    session_factory=session_factory,
                    vector_index=vector_index,
                    namespaces=(
                        settings.pinecone_user_memory_namespace,
                        settings.pinecone_documents_namespace,
                    ),
                    interval_seconds=settings.vector_reconciliation_interval_seconds,
                )
            )
            resources.append(
                MemoryRetentionJob(
                    session_factory=session_factory,
                    vector_index=vector_index,
                    batch_size=settings.memory_retention_batch_size,
                    poll_interval_seconds=settings.memory_retention_poll_interval_seconds,
                )
            )
            if settings.consolidation_enabled and settings.chat_api_key is not None:
                resources.append(
                    ConsolidationWorker(
                        session_factory=session_factory,
                        fact_extractor=LlmFactExtractor(
                            llm=LangChainChatModelFactory(settings).build()
                        ),
                        fact_policy=FactAcceptancePolicy(
                            max_statement_characters=settings.fact_max_statement_characters,
                            rederivable_terms=assistant.rederivable_terms
                            if assistant is not None
                            else frozenset(),
                        ),
                        candidate_store=FactCandidateRepository(
                            session_factory=session_factory,
                            retention_days=settings.fact_candidate_retention_days,
                        ),
                        fact_promoter=FactPromoter(
                            memory_store=MemoryRecordRepository(
                                session_factory=session_factory,
                                embedding_model=settings.embedding_model,
                                user_memory_namespace=settings.pinecone_user_memory_namespace,
                                documents_namespace=settings.pinecone_documents_namespace,
                            )
                        ),
                        tool_permissions_by_name={
                            tool.definition.name: tool.definition.required_permission.value for tool in assistant_tools
                        },
                        idle_minutes=settings.consolidation_idle_minutes,
                    )
                )
        if documents is not None:
            resources.extend(documents.resources)

        return cls(
            settings=settings,
            engine=database_engine,
            session_factory=session_factory,
            users=users,
            assistant=assistant,
            # langchain_smoke_check=build_langchain_smoke_check(settings),
            documents=documents,
            _resources=tuple(resources),
            operations=operations,
        )

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("Cannot start a closed container")

        if self._started:
            return

        try:
            for resource in self._resources:
                await resource.start()
                self._started_resources.append(resource)
        except BaseException as start_error:
            cleanup_errors: list[BaseException] = []

            for resource in reversed(self._started_resources):
                try:
                    await resource.stop()
                except BaseException as cleanup_error:
                    cleanup_errors.append(cleanup_error)

            self._started_resources.clear()

            if cleanup_errors:
                raise BaseExceptionGroup(
                    "Container startup and rollback failed",
                    [start_error, *cleanup_errors],
                ) from start_error

            raise

        self._started = True

    async def close(self) -> None:
        if self._closed:
            return

        self._closed = True
        errors: list[BaseException] = []

        for resource in reversed(self._started_resources):
            try:
                await resource.stop()
            except BaseException as error:
                errors.append(error)

        self._started_resources.clear()
        self._started = False

        try:
            await self.engine.dispose()
        except BaseException as error:
            errors.append(error)

        if errors:
            raise BaseExceptionGroup(
                "One or more container resources failed to close",
                errors,
            )


def get_container(request: Request) -> Container:
    return cast(Container, request.app.state.container)
