import json
from dataclasses import asdict, dataclass
from typing import cast

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.modules.assistant.infrastructure.agents.langchain.agent_orchestrator import (
    AgentDecision,
    AgentFinalResponse,
)
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState, PlannedAction


@dataclass(slots=True)
class AgentBrain:
    """Uses structured LLM output while leaving graph control flow deterministic."""

    llm: ChatOpenAI

    async def classify_intent(self, state: GraphState) -> str:
        del state
        return "assistant_query"

    async def plan_action(self, state: GraphState) -> PlannedAction:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are an orchestration agent. Use only the provided tools. "
                        "If no tool is needed, respond directly."
                    ),
                ),
                (
                    "human",
                    (
                        "User query:\n{user_query}\n\n"
                        "Intent:\n{intent}\n\n"
                        "Conversation history:\n{history_json}\n\n"
                        "Callable tools:\n{tools_json}\n\n"
                        "Tool call results:\n{tool_calls_json}\n\n"
                        "Remaining tool calls: {remaining_tool_calls}\n\n"
                        "Return action=respond or action=tool_call. For action=tool_call, "
                        "set tool_payload_json to a JSON-encoded object string. For "
                        "action=respond, set tool_payload_json to null."
                    ),
                ),
            ]
        )
        chain = prompt | self.llm.with_structured_output(AgentDecision)
        raw_decision = await chain.ainvoke(
            {
                "user_query": state["user_query"],
                "intent": state["intent"],
                "history_json": json.dumps(
                    [asdict(turn) for turn in state["conversation_history"]],
                    default=str,
                ),
                "tools_json": json.dumps(
                    [asdict(tool) for tool in state["available_tools"]],
                    default=str,
                ),
                "tool_calls_json": json.dumps(
                    [asdict(call) for call in state["tool_calls"]],
                    default=str,
                ),
                "remaining_tool_calls": state["remaining_tool_calls"],
            }
        )
        decision = (
            AgentDecision.model_validate(raw_decision)
            if isinstance(raw_decision, dict)
            else cast(AgentDecision, raw_decision)
        )
        return {
            "action": decision.action,
            "tool_name": decision.tool_name,
            "payload": decision.parse_tool_payload(),
        }

    async def respond(self, state: GraphState) -> str:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an orchestration agent. Produce a final answer using the supplied results.",
                ),
                (
                    "human",
                    (
                        "User query:\n{user_query}\n\n"
                        "Conversation history:\n{history_json}\n\n"
                        "Tool call results:\n{tool_calls_json}\n\n"
                        "Produce the final answer."
                    ),
                ),
            ]
        )
        chain = prompt | self.llm.with_structured_output(AgentFinalResponse)
        raw_response = await chain.ainvoke(
            {
                "user_query": state["user_query"],
                "history_json": json.dumps(
                    [asdict(turn) for turn in state["conversation_history"]],
                    default=str,
                ),
                "tool_calls_json": json.dumps(
                    [asdict(call) for call in state["tool_calls"]],
                    default=str,
                ),
            }
        )
        response = (
            AgentFinalResponse.model_validate(raw_response)
            if isinstance(raw_response, dict)
            else cast(AgentFinalResponse, raw_response)
        )
        return response.final_answer