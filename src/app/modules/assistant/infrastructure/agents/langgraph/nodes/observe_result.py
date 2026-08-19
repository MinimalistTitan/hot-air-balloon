from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState


async def observe_result(state: GraphState) -> dict[str, object]:
	pending_call = state["pending_call"]
	if pending_call is None:
		return {}

	per_tool_calls = dict(state["per_tool_calls"])
	per_tool_calls[pending_call.tool_name] = per_tool_calls.get(pending_call.tool_name, 0) + 1
	return {
		"pending_call": None,
		"tool_calls": [*state["tool_calls"], pending_call],
		"total_tool_calls": state["total_tool_calls"] + 1,
		"per_tool_calls": per_tool_calls,
		"remaining_tool_calls": state["remaining_tool_calls"] - 1,
	}
