from typing import Literal

from app.modules.assistant.domain.entities import (
    DecisionOutcome,
    DecisionStage,
)
from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.decision_observability import (
    record_decision,
)
from app.modules.assistant.infrastructure.agents.langgraph.semantic_validation import (
    validate_tool_call_semantics,
)
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState
from langgraph.runtime import Runtime
from langgraph.types import Command

ToolCallDestination = Literal["observe_result", "respond"]


async def invoke_tool(
    state: GraphState,
    runtime: Runtime[GraphContext],
) -> Command[ToolCallDestination]:
    action = state["planned_action"]
    tool_name = action["tool_name"]
    callable_names = {tool.name for tool in runtime.context.available_tools}
    can_call = tool_name in callable_names and runtime.context.call_budget.can_call(tool_name)
    if not can_call:
        record_decision(
            runtime.context,
            stage=DecisionStage.PRE_EXECUTION,
            outcome=DecisionOutcome.BLOCKED,
            source="policy",
            intent=action.get("intent", state["intent"] or None),
            confidence=action.get("confidence"),
            action="tool_call",
            tool_name=tool_name or None,
            reason_code="tool_call_policy",
        )
        return Command(
            update={
                "answer": "Tool call blocked by policy.",
                "finish_reason": OrchestrationFinishReason.POLICY_BLOCKED,
            },
            goto="respond",
        )

    payload = dict(action["payload"])
    descriptor = next(tool for tool in runtime.context.available_tools if tool.name == tool_name)
    semantic_result = validate_tool_call_semantics(
        query=runtime.context.user_query,
        descriptor=descriptor,
        payload=payload,
    )
    if not semantic_result.allowed:
        record_decision(
            runtime.context,
            stage=DecisionStage.PRE_EXECUTION,
            outcome=DecisionOutcome.BLOCKED,
            source="semantic_validator",
            intent=action.get("intent", state["intent"] or None),
            confidence=action.get("confidence"),
            action="tool_call",
            tool_name=tool_name,
            reason_code=(semantic_result.reason.value if semantic_result.reason else "unknown"),
        )
        return Command(
            update={
                "answer": "Tool call blocked because it did not match the user's request.",
                "finish_reason": OrchestrationFinishReason.POLICY_BLOCKED,
            },
            goto="respond",
        )

    record_decision(
        runtime.context,
        stage=DecisionStage.PRE_EXECUTION,
        outcome=DecisionOutcome.ALLOWED,
        source="semantic_validator",
        intent=action.get("intent", state["intent"] or None),
        confidence=action.get("confidence"),
        action="tool_call",
        tool_name=tool_name,
    )

    record_decision(
        runtime.context,
        stage=DecisionStage.RESULT_VALIDATION,
        outcome=DecisionOutcome.ALLOWED,
        source="result_validator",
        intent=action.get("intent", state["intent"] or None),
        confidence=action.get("confidence"),
        action="tool_call",
        tool_name=tool_name,
    )

    tool_call = await runtime.context.tool_invoker(tool_name, payload)

    if tool_call.tool_name != tool_name:
        return Command(
            update={
                "answer": "Tool call result blocked because its identity was invalid.",
                "finish_reason": OrchestrationFinishReason.POLICY_BLOCKED,
            },
            goto="respond",
        )

    return Command(update={"pending_call": tool_call}, goto="observe_result")
