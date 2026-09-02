from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState
from langgraph.runtime import Runtime


async def classify_intent(
    state: GraphState,
    runtime: Runtime[GraphContext],
) -> dict[str, str]:
    return {
        "intent": await runtime.context.brain.classify_intent(runtime.context.agent_state(state))
    }
