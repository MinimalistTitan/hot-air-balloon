from typing import Any

from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext
from app.modules.assistant.infrastructure.agents.langgraph.nodes.classify_intent import (
	classify_intent,
)
from app.modules.assistant.infrastructure.agents.langgraph.nodes.decide_next_step import (
	decide_next_step,
)
from app.modules.assistant.infrastructure.agents.langgraph.nodes.observe_result import (
	observe_result,
)
from app.modules.assistant.infrastructure.agents.langgraph.nodes.plan_action import plan_action
from app.modules.assistant.infrastructure.agents.langgraph.nodes.respond import respond
from app.modules.assistant.infrastructure.agents.langgraph.nodes.tool_call import invoke_tool
from app.modules.assistant.infrastructure.agents.langgraph.routing import (
	route_after_decision,
	route_after_plan_action,
	route_after_tool_call,
)
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


def build_workflow(
	checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[GraphState, GraphContext, GraphState, GraphState]:
	graph = StateGraph(GraphState, context_schema=GraphContext)
	graph.add_node("classify_intent", classify_intent)
	graph.add_node("plan_action", plan_action)
	graph.add_node("tool_call", invoke_tool)
	graph.add_node("observe_result", observe_result)
	graph.add_node("decide_next_step", decide_next_step)
	graph.add_node("respond", respond)

	graph.add_edge(START, "classify_intent")
	graph.add_edge("classify_intent", "plan_action")
	graph.add_conditional_edges("plan_action", route_after_plan_action)
	graph.add_conditional_edges("tool_call", route_after_tool_call)
	graph.add_edge("observe_result", "decide_next_step")
	graph.add_conditional_edges("decide_next_step", route_after_decision)
	graph.add_edge("respond", END)
	return graph.compile(checkpointer=checkpointer)
