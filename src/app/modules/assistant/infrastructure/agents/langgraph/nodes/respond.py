from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState
from langgraph.runtime import Runtime


async def respond(
	state: GraphState,
	runtime: Runtime[GraphContext],
) -> dict[str, object]:
	if state["finish_reason"] is not None:
		return {}

	answer = await runtime.context.brain.respond(state)
	return {
		"answer": answer.strip() or "No answer generated.",
		"finish_reason": OrchestrationFinishReason.COMPLETED,
	}
