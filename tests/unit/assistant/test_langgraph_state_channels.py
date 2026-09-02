from uuid import UUID

from langgraph.checkpoint.memory import InMemorySaver

from app.modules.assistant.domain.context import AssembledContext, ContextBlock, ContextKind
from app.modules.assistant.domain.entities import (
    ToolCallRecord,
    ToolDescriptor,
    ToolOutcomeStatus,
)
from app.modules.assistant.domain.tool_call import ToolCallPolicy
from app.modules.assistant.infrastructure.agents.langgraph.orchestrator import (
    LangGraphAgentOrchestrator,
)
from app.modules.assistant.infrastructure.agents.langgraph.state import (
    CURRENT_WORKFLOW_VERSION,
    AgentStateView,
    PlannedAction,
)
from app.modules.assistant.infrastructure.agents.langgraph.thread_identity import derive_thread_id
from app.modules.user.domain.authorization import AuthorizationContext, RoleName
from app.shared.kernel.response_evidence import FailureEvidence

OWNER_ID = UUID("11111111-1111-1111-1111-111111111111")
CONVERSATION_ID = UUID("22222222-2222-2222-2222-222222222222")


class RecordingDirectResponseBrain:
    def __init__(self) -> None:
        self.states: list[AgentStateView] = []

    async def classify_intent(self, state: AgentStateView) -> str:
        self.states.append(state)
        return "assistant_query"

    async def plan_action(self, state: AgentStateView) -> PlannedAction:
        self.states.append(state)
        return {"action": "respond", "tool_name": "", "payload": {}}

    async def respond(self, state: AgentStateView) -> str:
        self.states.append(state)
        return "Transient response"


async def _fail_invoker(
    tool_name: str,
    payload: dict[str, object],
) -> ToolCallRecord:
    del tool_name, payload
    raise AssertionError("No tool call is expected")


def _authorization() -> AuthorizationContext:
    return AuthorizationContext(
        user_id=OWNER_ID,
        roles=frozenset({RoleName.READ_ONLY_ANALYST}),
        global_scope=True,
    )


async def test_checkpoint_contains_only_durable_application_channels() -> None:
    saver = InMemorySaver()
    brain = RecordingDirectResponseBrain()
    orchestrator = LangGraphAgentOrchestrator(
        brain=brain,
        model_name="test-model",
        checkpointer=saver,
    )
    sentinel_context = "TRANSIENT-RETRIEVED-CONTEXT"
    query = "TRANSIENT-USER-QUERY"
    tool_name = "transient_tool_descriptor"

    result = await orchestrator.run(
        conversation_id=CONVERSATION_ID,
        authorization_context=_authorization(),
        user_query=query,
        available_tools=[ToolDescriptor(name=tool_name, description="transient")],
        tool_invoker=_fail_invoker,
        context=AssembledContext(
            blocks=[
                ContextBlock(
                    kind=ContextKind.SYSTEM_DIRECTIVE,
                    content=sentinel_context,
                    source="test",
                )
            ]
        ),
        tool_policy=ToolCallPolicy(
            allowed_tool_names=frozenset({tool_name}),
            max_total_calls=1,
            max_calls_per_tool=1,
        ),
        max_tool_calls=1,
        allow_tool_calls=True,
    )

    assert result.answer == "Transient response"
    checkpoint = await saver.aget(
        {
            "configurable": {
                "thread_id": derive_thread_id(
                    owner_user_id=OWNER_ID,
                    conversation_id=CONVERSATION_ID,
                )
            }
        }
    )
    assert checkpoint is not None
    channel_values = checkpoint["channel_values"]
    assert channel_values["workflow_version"] == CURRENT_WORKFLOW_VERSION
    assert {
        "intent",
        "planned_action",
        "pending_call",
        "tool_calls",
        "next_step",
        "answer",
        "finish_reason",
        "total_tool_calls",
        "per_tool_calls",
        "remaining_tool_calls",
        "max_calls_per_tool",
    }.isdisjoint(channel_values)

    serialized_checkpoint = repr(checkpoint)
    assert query not in serialized_checkpoint
    assert sentinel_context not in serialized_checkpoint
    assert tool_name not in serialized_checkpoint
    assert str(OWNER_ID) not in serialized_checkpoint

    assert brain.states
    assert brain.states[-1]["user_query"] == query
    assert sentinel_context in brain.states[-1]["context_prompt"]
    assert brain.states[-1]["available_tools"][0].name == tool_name


class OneToolBrain:
    async def classify_intent(self, state: AgentStateView) -> str:
        del state
        return "lookup"

    async def plan_action(self, state: AgentStateView) -> PlannedAction:
        del state
        return {
            "action": "tool_call",
            "tool_name": "lookup",
            "payload": {"id": "A-1"},
        }

    async def respond(self, state: AgentStateView) -> str:
        del state
        raise AssertionError("Tool evidence must use the deterministic composer")


async def test_raw_tool_result_and_call_budget_are_not_checkpointed() -> None:
    saver = InMemorySaver()
    raw_result_marker = "RAW-TOOL-RESULT-MUST-NOT-BE-DURABLE"

    async def invoke_tool(
        tool_name: str,
        payload: dict[str, object],
    ) -> ToolCallRecord:
        return ToolCallRecord(
            tool_name=tool_name,
            payload=payload,
            status=ToolOutcomeStatus.FAILED,
            evidence=(
                FailureEvidence(
                    evidence_id="failure-A-1",
                    code="not_found",
                    message="Asset was not found",
                    retryable=False,
                ),
            ),
            result={"private_backend_payload": raw_result_marker},
        )

    orchestrator = LangGraphAgentOrchestrator(
        brain=OneToolBrain(),
        model_name="test-model",
        checkpointer=saver,
    )
    result = await orchestrator.run(
        conversation_id=CONVERSATION_ID,
        authorization_context=_authorization(),
        user_query="Look up A-1",
        available_tools=[ToolDescriptor(name="lookup", description="lookup")],
        tool_invoker=invoke_tool,
        context=AssembledContext(),
        tool_policy=ToolCallPolicy(
            allowed_tool_names=frozenset({"lookup"}),
            max_total_calls=1,
            max_calls_per_tool=1,
        ),
        max_tool_calls=1,
        allow_tool_calls=True,
    )

    assert result.tool_calls[0].result["private_backend_payload"] == raw_result_marker
    checkpoint = await saver.aget(
        {
            "configurable": {
                "thread_id": derive_thread_id(
                    owner_user_id=OWNER_ID,
                    conversation_id=CONVERSATION_ID,
                )
            }
        }
    )
    assert checkpoint is not None
    assert raw_result_marker not in repr(checkpoint)
    checkpoint_history = [
        item
        async for item in saver.alist(
            {
                "configurable": {
                    "thread_id": derive_thread_id(
                        owner_user_id=OWNER_ID,
                        conversation_id=CONVERSATION_ID,
                    )
                }
            }
        )
    ]
    assert raw_result_marker not in repr(checkpoint_history)
