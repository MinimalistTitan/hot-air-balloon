from typing import Literal

from app.modules.assistant.domain.entities import DecisionOutcome, DecisionStage
from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.decision_observability import (
    record_decision,
)
from app.modules.assistant.infrastructure.agents.langgraph.deterministic_intent import (
    resolve_intent,
)
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState, PlannedAction
from langgraph.runtime import Runtime
from langgraph.types import Command

PlanDestination = Literal["tool_call", "respond"]


def _route(action: PlannedAction) -> Command[PlanDestination]:
    destination: PlanDestination = "tool_call" if action["action"] == "tool_call" else "respond"
    update: dict[str, object] = {"planned_action": action}
    if action["action"] == "respond" and action.get("answer"):
        update["answer"] = action["answer"]
        update["finish_reason"] = OrchestrationFinishReason.COMPLETED
    return Command(update=update, goto=destination)


async def plan_action(
    state: GraphState,
    runtime: Runtime[GraphContext],
) -> Command[PlanDestination]:
    callable_tools = [
        tool
        for tool in runtime.context.available_tools
        if runtime.context.call_budget.can_call(tool.name)
    ]

    resolution = resolve_intent(runtime.context.user_query)
    if resolution is not None:
        callable_tool_names = {tool.name for tool in callable_tools}
        if resolution.tool_name is None or resolution.tool_name not in callable_tool_names:
            reason_code = (
                "direct_response_intent"
                if resolution.tool_name is None
                else "target_tool_unavailable"
            )
            record_decision(
                runtime.context,
                stage=DecisionStage.PLANNING,
                outcome=(
                    DecisionOutcome.SELECTED
                    if resolution.tool_name is None
                    else DecisionOutcome.BLOCKED
                ),
                source="deterministic",
                intent=resolution.intent.value,
                confidence=1.0,
                action="respond",
                tool_name=resolution.tool_name,
                reason_code=reason_code,
                callable_tool_count=len(callable_tools),
            )
            return _route(
                {
                    "action": "respond",
                    "tool_name": "",
                    "payload": {},
                }
            )

        record_decision(
            runtime.context,
            stage=DecisionStage.PLANNING,
            outcome=DecisionOutcome.SELECTED,
            source="deterministic",
            intent=resolution.intent.value,
            confidence=1.0,
            action="tool_call",
            tool_name=resolution.tool_name,
            callable_tool_count=len(callable_tools),
        )

        return _route(
            {
                "action": "tool_call",
                "tool_name": resolution.tool_name,
                "payload": resolution.payload,
            }
        )

    if not callable_tools:
        record_decision(
            runtime.context,
            stage=DecisionStage.PLANNING,
            outcome=DecisionOutcome.BLOCKED,
            source="policy",
            intent=state["intent"] or None,
            action="respond",
            reason_code="no_callable_tools",
            callable_tool_count=0,
        )
        return _route(
            {
                "action": "respond",
                "tool_name": "",
                "payload": {},
            }
        )

    planning_state = runtime.context.agent_state(state, available_tools=callable_tools)
    planned_action = await runtime.context.brain.plan_action(planning_state)
    confidence = planned_action.get("confidence")
    record_decision(
        runtime.context,
        stage=DecisionStage.PLANNING,
        outcome=DecisionOutcome.SELECTED,
        source="model",
        intent=planned_action.get("intent", state["intent"] or None),
        confidence=confidence,
        action=planned_action["action"],
        tool_name=planned_action["tool_name"] or None,
        reason_code=(
            "low_confidence_response" if confidence is not None and confidence < 0.8 else None
        ),
        callable_tool_count=len(callable_tools),
    )
    return _route(planned_action)
