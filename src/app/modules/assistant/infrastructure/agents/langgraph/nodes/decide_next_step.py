from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState
from langgraph.runtime import Runtime


async def decide_next_step(
    state: GraphState,
    runtime: Runtime[GraphContext],
) -> dict[str, str]:
    del state
    next_step = "continue" if runtime.context.call_budget.remaining_calls > 0 else "respond"
    return {"next_step": next_step}
