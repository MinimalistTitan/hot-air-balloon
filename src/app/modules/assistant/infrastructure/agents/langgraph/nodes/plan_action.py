from typing import cast

from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
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
    if not callable_tools:
        return {
            "planned_action": {
                "action": "respond",
                "tool_name": "",
                "payload": {},
            }
        }

    planning_state = cast(GraphState, dict(state))
    planning_state["available_tools"] = callable_tools
    return {"planned_action": await runtime.context.brain.plan_action(planning_state)}
