from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.container import Container
from app.core.config import Settings
from app.modules.assistant.application.ports import ToolInvoker
from app.modules.assistant.domain.context import AssembledContext
from app.modules.assistant.domain.entities import AgentRunResult, ToolDescriptor
from app.modules.assistant.domain.tool_call import ToolCallPolicy
from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from app.modules.assistant.infrastructure.agents.langgraph import (
    orchestrator as orchestrator_module,
)
from app.modules.assistant.infrastructure.agents.langgraph import (
    postgres_checkpointer as checkpointer_module,
)
from app.modules.assistant.infrastructure.agents.langgraph.orchestrator import (
    LangGraphAgentOrchestrator,
)
from app.modules.assistant.infrastructure.agents.langgraph.postgres_checkpointer import (
    PostgresCheckpointer,
)


class RecordingPool:
    def __init__(self, **_: object) -> None:
        self.open_calls: list[bool] = []
        self.close_calls = 0

    async def open(self, *args: object, **kwargs: object) -> None:
        del args
        self.open_calls.append(bool(kwargs.get("wait", False)))

    async def close(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self.close_calls += 1


class RecordingSaver:
    def __init__(self, pool: RecordingPool) -> None:
        self.pool = pool
        self.setup_calls = 0

    async def setup(self) -> None:
        self.setup_calls += 1


class FailingSaver(RecordingSaver):
    async def setup(self) -> None:
        self.setup_calls += 1
        raise RuntimeError("setup failed")


class ManagedFakeAgent:
    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def run(
        self,
        conversation_id: UUID,
        user_query: str,
        available_tools: list[ToolDescriptor],
        tool_invoker: ToolInvoker,
        context: AssembledContext,
        tool_policy: ToolCallPolicy,
        max_tool_calls: int,
        allow_tool_calls: bool,
    ) -> AgentRunResult:
        del (
            conversation_id,
            user_query,
            available_tools,
            tool_invoker,
            context,
            tool_policy,
            max_tool_calls,
            allow_tool_calls,
        )
        return AgentRunResult(
            answer="unused",
            agent_name="test",
            model_name="test",
            finish_reason=OrchestrationFinishReason.COMPLETED,
            tool_calls=[],
            evidence=(),
        )


def _postgres_url() -> str:
    return "postgresql+asyncpg://postgres:password@localhost:5432/assistant"


async def test_postgres_checkpointer_starts_once_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checkpointer_module, "AsyncConnectionPool", RecordingPool)
    monkeypatch.setattr(checkpointer_module, "AsyncPostgresSaver", RecordingSaver)
    checkpointer = PostgresCheckpointer(_postgres_url())

    await checkpointer.start()
    await checkpointer.start()

    pool = cast(RecordingPool, checkpointer._pool)
    saver = cast(RecordingSaver, checkpointer.saver)
    assert pool.open_calls == [True]
    assert saver.setup_calls == 1

    await checkpointer.stop()
    await checkpointer.stop()

    assert pool.close_calls == 1
    with pytest.raises(RuntimeError, match="has not been started"):
        _ = checkpointer.saver


async def test_postgres_checkpointer_closes_pool_when_setup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checkpointer_module, "AsyncConnectionPool", RecordingPool)
    monkeypatch.setattr(checkpointer_module, "AsyncPostgresSaver", FailingSaver)
    checkpointer = PostgresCheckpointer(_postgres_url())

    with pytest.raises(RuntimeError, match="setup failed"):
        await checkpointer.start()

    pool = cast(RecordingPool, checkpointer._pool)
    assert pool.open_calls == [True]
    assert pool.close_calls == 1
    with pytest.raises(RuntimeError, match="has not been started"):
        _ = checkpointer.saver


async def test_orchestrator_compiles_after_managed_checkpointer_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checkpointer_module, "AsyncConnectionPool", RecordingPool)
    checkpointer = PostgresCheckpointer(_postgres_url())
    saver = object()
    checkpointer._saver = cast(Any, saver)
    checkpointer._started = True

    compiled_with: list[object] = []

    def build_workflow(checkpointer_arg: object) -> object:
        compiled_with.append(checkpointer_arg)
        return object()

    monkeypatch.setattr(orchestrator_module, "build_workflow", build_workflow)
    orchestrator = LangGraphAgentOrchestrator(
        brain=cast(Any, object()),
        model_name="test-model",
        checkpointer=checkpointer,
    )

    assert orchestrator._workflow is None
    assert compiled_with == []

    await orchestrator.start()

    assert compiled_with == [saver]
    assert orchestrator._workflow is not None

    await orchestrator.stop()
    assert orchestrator._workflow is None


async def test_container_orders_managed_checkpointer_before_orchestrator() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    settings = Settings(
        database_url=_postgres_url(),
        assistant_checkpointing_enabled=True,
    )
    agent = ManagedFakeAgent()
    container = Container.build(
        settings,
        engine,
        assistant_agent_orchestrator=agent,
    )

    try:
        resources = container._resources
        checkpointer_index = next(
            index
            for index, resource in enumerate(resources)
            if isinstance(resource, PostgresCheckpointer)
        )
        assert resources[checkpointer_index + 1] is agent
    finally:
        await container.close()
