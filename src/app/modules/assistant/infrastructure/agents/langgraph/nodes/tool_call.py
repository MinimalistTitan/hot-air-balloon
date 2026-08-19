from app.modules.assistant.domain.entities import ToolCallRecord
from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState
from langgraph.runtime import Runtime


async def invoke_tool(
	state: GraphState,
	runtime: Runtime[GraphContext],
) -> dict[str, object]:
	action = state["planned_action"]
	tool_name = action["tool_name"]
	callable_names = {tool.name for tool in state["available_tools"]}
	can_call = (
		state["remaining_tool_calls"] > 0
		and tool_name in callable_names
		and state["per_tool_calls"].get(tool_name, 0) < state["max_calls_per_tool"]
	)
	if not can_call:
		return {
			"answer": "Tool call blocked by policy.",
			"finish_reason": OrchestrationFinishReason.POLICY_BLOCKED,
		}

	payload = dict(action["payload"])
	tool_result = await runtime.context.tool_invoker(tool_name, payload)
	sanitized_result = dict(tool_result)
	sanitized_result.pop("tool_name", None)
	return {
		"pending_call": ToolCallRecord(
			tool_name=tool_name,
			payload=payload,
			result=sanitized_result,
		)
	}
