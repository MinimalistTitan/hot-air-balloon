from typing import Literal

from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState


def route_after_plan_action(state: GraphState) -> Literal["tool_call", "respond"]:
	if state["planned_action"]["action"] == "tool_call":
		return "tool_call"
	return "respond"


def route_after_tool_call(state: GraphState) -> Literal["observe_result", "respond"]:
	if state["finish_reason"] is not None:
		return "respond"
	return "observe_result"


def route_after_decision(state: GraphState) -> Literal["plan_action", "respond"]:
	if state["next_step"] == "continue":
		return "plan_action"
	return "respond"
