from typing import cast

from app.modules.assistant.domain.entities import DecisionOutcome, DecisionStage
from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.decision_observability import (
    record_decision,
)
from app.modules.assistant.infrastructure.agents.langgraph.deterministic_intent import (
    resolve_intent,
)
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState, PlannedAction
from langgraph.runtime import Runtime


async def plan_action(
    state: GraphState,
    runtime: Runtime[GraphContext],
) -> dict[str, PlannedAction]:
    callable_tools = [
        tool
        for tool in state["available_tools"]
        if state["remaining_tool_calls"] > 0
        and state["per_tool_calls"].get(tool.name, 0) < state["max_calls_per_tool"]
    ]

    resolution = resolve_intent(state["user_query"])
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
            return {
                "planned_action": {
                    "action": "respond",
                    "tool_name": "",
                    "payload": {},
                }
            }

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

        return {
            "planned_action": {
                "action": "tool_call",
                "tool_name": resolution.tool_name,
                "payload": resolution.payload,
            }
        }

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
        return {
            "planned_action": {
                "action": "respond",
                "tool_name": "",
                "payload": {},
            }
        }

    planning_state = cast(GraphState, dict(state))
    planning_state["available_tools"] = callable_tools
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
    return {"planned_action": planned_action}
