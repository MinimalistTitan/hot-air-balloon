from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState
from langgraph.runtime import Runtime


async def observe_result(
    state: GraphState,
    runtime: Runtime[GraphContext],
) -> dict[str, object]:
    pending_call = state["pending_call"]
    if pending_call is None:
        return {}

    runtime.context.call_budget.record(pending_call.tool_name)
    return {
        "pending_call": None,
        "tool_calls": [*state["tool_calls"], pending_call],
    }
