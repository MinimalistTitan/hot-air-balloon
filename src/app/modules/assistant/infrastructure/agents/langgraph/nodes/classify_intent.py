from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.state import (
    ConversationWorkingSet,
    GraphState,
)
from langgraph.runtime import Runtime


async def classify_intent(
    state: GraphState,
    runtime: Runtime[GraphContext],
) -> dict[str, object]:
    intent = await runtime.context.brain.classify_intent(runtime.context.agent_state(state))
    working_set: ConversationWorkingSet = {
        "active_intent": intent,
        "referenced_entities": list(state["working_set"]["referenced_entities"]),
    }
    return {"intent": intent, "working_set": working_set}
