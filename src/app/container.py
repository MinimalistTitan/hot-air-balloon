from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Self, cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.database.database import SessionFactory, create_engine, create_session_factory
from app.core.life_cycle import ManagedResource
from app.modules.assistant.application.ports import (
    AgentOrchestratorPort,
    AssistantTelemetryPort,
    ConversationStorePort,
    ToolRuntimePort,
)
from app.modules.assistant.domain.ports.web_search import WebSearchPort
from app.modules.assistant.domain.tool_call import ToolCallPolicy
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

        assistant = build_assistant_module(
            settings=settings,
            tools=(*users.tools, *operations.tools, *operations.write_tools),
            session_factory=session_factory,
            web_search_provider=web_search_provider,
            tool_runtime=assistant_tool_runtime,
            agent_orchestrator=assistant_agent_orchestrator,
            conversation_store=assistant_conversation_store,
            telemetry=assistant_telemetry,
            tool_policy=assistant_tool_policy,
        )

        resources = list(managed_resources)
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