from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState


async def decide_next_step(state: GraphState) -> dict[str, str]:
	next_step = "continue" if state["remaining_tool_calls"] > 0 else "respond"
	return {"next_step": next_step}
