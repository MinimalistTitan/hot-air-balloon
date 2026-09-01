from typing import Any, cast
from uuid import UUID, uuid4

from langchain_core.runnables.config import RunnableConfig

from app.modules.assistant.domain.context import AssembledContext
from app.modules.assistant.domain.entities import ToolCallRecord
from app.modules.assistant.domain.tool_call import ToolCallPolicy
from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.orchestrator import (
    CompiledWorkflow,
    LangGraphAgentOrchestrator,
)
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState
from app.modules.assistant.infrastructure.agents.langgraph.thread_identity import (
    THREAD_ID_PREFIX,
    derive_thread_id,
)
from app.modules.user.domain.authorization import AuthorizationContext, RoleName

OWNER_ID = UUID("11111111-1111-1111-1111-111111111111")
CONVERSATION_ID = UUID("22222222-2222-2222-2222-222222222222")
EXPECTED_THREAD_ID = "assistant:v1:06266d9aebe4f75cc68199b247ec04d51fa86e22b119c2891ee2ea5281efc255"


class RecordingWorkflow:
    def __init__(self) -> None:
        self.config: RunnableConfig | None = None

    async def ainvoke(
        self,
        graph_input: GraphState,
        config: RunnableConfig | None = None,
        *,
        context: GraphContext | None = None,
    ) -> object:
        del context
        self.config = config
        result = dict(graph_input)
        result["answer"] = "Completed"
        result["finish_reason"] = OrchestrationFinishReason.COMPLETED
        return result


async def _fail_invoker(
    tool_name: str,
    payload: dict[str, object],
) -> ToolCallRecord:
    del tool_name, payload
    raise AssertionError("The thread identity test must not invoke tools")


def _authorization(owner_user_id: UUID) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=owner_user_id,
        roles=frozenset({RoleName.READ_ONLY_ANALYST}),
        global_scope=True,
    )


def test_thread_id_has_stable_versioned_fixed_vector() -> None:
    thread_id = derive_thread_id(
        owner_user_id=OWNER_ID,
        conversation_id=CONVERSATION_ID,
    )

    assert thread_id == EXPECTED_THREAD_ID
    assert thread_id.startswith(THREAD_ID_PREFIX)
    assert len(thread_id) == 77
    assert str(OWNER_ID) not in thread_id
    assert str(CONVERSATION_ID) not in thread_id


def test_thread_id_changes_when_either_trusted_component_changes() -> None:
    original = derive_thread_id(
        owner_user_id=OWNER_ID,
        conversation_id=CONVERSATION_ID,
    )

    assert (
        derive_thread_id(
            owner_user_id=uuid4(),
            conversation_id=CONVERSATION_ID,
        )
        != original
    )
    assert (
        derive_thread_id(
            owner_user_id=OWNER_ID,
            conversation_id=uuid4(),
        )
        != original
    )


async def test_langgraph_uses_only_derived_thread_id_in_config() -> None:
    workflow = RecordingWorkflow()
    orchestrator = LangGraphAgentOrchestrator(
        brain=cast(Any, object()),
        model_name="test-model",
    )
    orchestrator._workflow = cast(CompiledWorkflow, workflow)

    await orchestrator.run(
        conversation_id=CONVERSATION_ID,
        authorization_context=_authorization(OWNER_ID),
        user_query="Hello",
        available_tools=[],
        tool_invoker=_fail_invoker,
        context=AssembledContext(),
        tool_policy=ToolCallPolicy(
            allowed_tool_names=frozenset(),
            max_total_calls=0,
            max_calls_per_tool=0,
        ),
        max_tool_calls=0,
        allow_tool_calls=False,
    )

    assert workflow.config is not None
    configurable = cast(dict[str, object], workflow.config["configurable"])
    assert configurable == {"thread_id": EXPECTED_THREAD_ID}
