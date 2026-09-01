import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import status

from app.bootstrap.errors import ERROR_RESPONSES
from app.modules.assistant.application.commands import AssistantQueryCommand
from app.modules.assistant.application.context.providers import ContextRequest
from app.modules.assistant.application.ports import ToolInvoker
from app.modules.assistant.application.use_cases import OrchestrateAssistantQuery
from app.modules.assistant.domain.context import AssembledContext
from app.modules.assistant.domain.entities import (
    AgentRunResult,
    AssistantDecisionEvent,
    ToolCallRecord,
    ToolDescriptor,
)
from app.modules.assistant.domain.errors import ConversationOwnershipError
from app.modules.assistant.domain.tool_call import ToolCallPolicy
from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from app.modules.assistant.infrastructure.conversation_memory.in_memory.inmemory_conversation_store import (
    InMemoryConversationStore,
)
from app.modules.user.domain.authorization import AuthorizationContext, RoleName


class RecordingContextAssembler:
    def __init__(self) -> None:
        self.calls: list[ContextRequest] = []

    async def assemble(self, request: ContextRequest) -> AssembledContext:
        self.calls.append(request)
        return AssembledContext()


class RecordingToolRuntime:
    def __init__(self) -> None:
        self.list_calls = 0
        self.invoke_calls = 0

    async def list_tools(
        self,
        authorization_context: AuthorizationContext,
    ) -> list[ToolDescriptor]:
        del authorization_context
        self.list_calls += 1
        return []

    async def invoke(
        self,
        tool_name: str,
        payload: dict[str, object],
        authorization_context: AuthorizationContext,
        conversation_id: UUID | None = None,
    ) -> ToolCallRecord:
        del tool_name, payload, authorization_context, conversation_id
        self.invoke_calls += 1
        raise AssertionError("No tool should be invoked in this test")


class RecordingAgent:
    def __init__(self) -> None:
        self.calls = 0
        self.authorization_contexts: list[AuthorizationContext] = []

    async def run(
        self,
        conversation_id: UUID,
        authorization_context: AuthorizationContext,
        user_query: str,
        available_tools: list[ToolDescriptor],
        tool_invoker: ToolInvoker,
        context: AssembledContext,
        tool_policy: ToolCallPolicy,
        max_tool_calls: int,
        allow_tool_calls: bool,
    ) -> AgentRunResult:
        self.authorization_contexts.append(authorization_context)
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
        self.calls += 1
        return AgentRunResult(
            answer="Completed answer",
            agent_name="test-agent",
            model_name="test-model",
            finish_reason=OrchestrationFinishReason.COMPLETED,
            tool_calls=[],
            evidence=(),
        )


class RecordingTelemetry:
    def __init__(self) -> None:
        self.started = 0
        self.completed = 0

    def query_started(self, query: str) -> None:
        del query
        self.started += 1

    def tool_called(self, tool_name: str) -> None:
        del tool_name

    def decision_recorded(self, event: AssistantDecisionEvent) -> None:
        del event

    def query_completed(self, tools_used: int) -> None:
        del tools_used
        self.completed += 1


def _authorization(user_id: UUID) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user_id,
        roles=frozenset({RoleName.READ_ONLY_ANALYST}),
        global_scope=True,
    )


def _use_case(
    store: InMemoryConversationStore,
) -> tuple[
    OrchestrateAssistantQuery,
    RecordingContextAssembler,
    RecordingToolRuntime,
    RecordingAgent,
    RecordingTelemetry,
]:
    assembler = RecordingContextAssembler()
    tools = RecordingToolRuntime()
    agent = RecordingAgent()
    telemetry = RecordingTelemetry()
    return (
        OrchestrateAssistantQuery(
            tool_runtime=tools,
            agent_orchestrator=agent,
            conversation_store=store,
            telemetry=telemetry,
            tool_policy=ToolCallPolicy(
                allowed_tool_names=frozenset(),
                max_total_calls=0,
                max_calls_per_tool=0,
            ),
            context_assembler=assembler,
        ),
        assembler,
        tools,
        agent,
        telemetry,
    )


async def test_cross_user_request_stops_before_context_tools_or_graph() -> None:
    store = InMemoryConversationStore()
    conversation_id = uuid4()
    owner_user_id = uuid4()
    other_user_id = uuid4()
    await store.claim_or_validate(conversation_id, owner_user_id, datetime.now(UTC))
    use_case, assembler, tools, agent, telemetry = _use_case(store)

    with pytest.raises(ConversationOwnershipError):
        await use_case.execute(
            AssistantQueryCommand(
                query="Show the previous conversation",
                authorization_context=_authorization(other_user_id),
                conversation_id=conversation_id,
            )
        )

    assert assembler.calls == []
    assert tools.list_calls == 0
    assert agent.calls == 0
    assert telemetry.started == 1
    assert telemetry.completed == 0
    assert await store.read_recent(conversation_id, owner_user_id) == []


async def test_completed_query_mirrors_one_atomic_exchange() -> None:
    store = InMemoryConversationStore()
    owner_user_id = uuid4()
    conversation_id = uuid4()
    use_case, assembler, tools, agent, telemetry = _use_case(store)

    response = await use_case.execute(
        AssistantQueryCommand(
            query="What is asset A-17?",
            authorization_context=_authorization(owner_user_id),
            conversation_id=conversation_id,
        )
    )

    turns = await store.read_recent(conversation_id, owner_user_id)
    assert [(turn.role, turn.content) for turn in turns] == [
        ("user", "What is asset A-17?"),
        ("assistant", "Completed answer"),
    ]
    assert turns[0].created_at_utc <= turns[1].created_at_utc
    assert response.conversation_id == conversation_id
    assert len(assembler.calls) == 1
    assert tools.list_calls == 1
    assert agent.calls == 1
    assert [context.user_id for context in agent.authorization_contexts] == [owner_user_id]
    assert telemetry.completed == 1


async def test_inmemory_first_owner_claim_is_atomic() -> None:
    store = InMemoryConversationStore()
    conversation_id = uuid4()
    first_user_id = uuid4()
    second_user_id = uuid4()
    observed_at = datetime.now(UTC)

    results = await asyncio.gather(
        store.claim_or_validate(conversation_id, first_user_id, observed_at),
        store.claim_or_validate(
            conversation_id,
            second_user_id,
            observed_at + timedelta(microseconds=1),
        ),
        return_exceptions=True,
    )

    assert sum(result is None for result in results) == 1
    assert sum(isinstance(result, ConversationOwnershipError) for result in results) == 1


def test_ownership_error_is_non_disclosing_not_found() -> None:
    response = ERROR_RESPONSES[ConversationOwnershipError]
    assert response == (
        status.HTTP_404_NOT_FOUND,
        "Conversation not found",
        "The requested conversation was not found.",
    )
