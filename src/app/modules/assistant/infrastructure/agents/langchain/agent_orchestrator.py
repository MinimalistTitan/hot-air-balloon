import json
from dataclasses import asdict, dataclass
from typing import Any, Literal, cast
from uuid import UUID

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.modules.assistant.application.ports import (
    AgentOrchestratorPort,
    ToolInvoker,
)
from app.modules.assistant.domain.context import AssembledContext
from app.modules.assistant.domain.entities import AgentRunResult, ToolCallRecord, ToolDescriptor
from app.modules.assistant.domain.tool_call import ToolCallBudgetState, ToolCallPolicy
from app.modules.assistant.domain.value_object import OrchestrationFinishReason

_TOOL_PAYLOAD_ADAPTER = TypeAdapter(dict[str, object])


class AgentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["respond", "tool_call"]
    final_answer: str
    tool_name: str
    tool_payload_json: str | None = Field(
        default=None,
        description="JSON-encoded object for a tool call; null when responding directly.",
    )

    def parse_tool_payload(self) -> dict[str, object]:
        if self.tool_payload_json is None:
            return {}
        return _TOOL_PAYLOAD_ADAPTER.validate_json(self.tool_payload_json)

class AgentFinalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_answer: str

@dataclass(slots=True)
class LangChainAgentOrchestrator(AgentOrchestratorPort):
    llm: ChatOpenAI
    agent_name: str = "assistant.default"

    async def run(
        self,
        conversation_id: UUID,
        user_query: str,
        available_tools: list[ToolDescriptor],
        tool_invoker: ToolInvoker,
        context: AssembledContext,
        tool_policy: ToolCallPolicy,
        max_tool_calls: int,
        allow_tool_calls: bool,
    ) -> AgentRunResult:
        del conversation_id
        tool_calls: list[ToolCallRecord] = []
        budget = ToolCallBudgetState()
        scratchpad: list[dict[str, Any]] = []

        effective_max_tool_calls = (
            min(max(max_tool_calls, 0), tool_policy.max_total_calls)
            if allow_tool_calls
            else 0
        )

        allowed_tools = [
            tool
            for tool in available_tools
            if tool.name in tool_policy.allowed_tool_names
        ]

        decision_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are an orchestration agent. "
                        "Use only the provided tools. "
                        "If no tool is needed, respond directly."
                        "Do not call the same tool more than once. "
                        "If the available tool results answer the request, respond directly."
                    ),
                ),
                (
                    "human",
                    (
                        "User query:\n{user_query}\n\n"
                        "Conversation history:\n{history_json}\n\n"
                        "Callable tools:\n{tools_json}\n\n"
                        "Tool call results:\n{scratchpad_json}\n\n"
                        "Remaining tool calls: {remaining_tool_calls}\n\n"
                        "Return action=respond or action=tool_call. "
                        "For action=tool_call, set tool_payload_json to a JSON-encoded "
                        "object string. For action=respond, set tool_payload_json to null."
                    ),
                ),
            ]
        )

        final_response_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are an orchestration agent. "
                        "Return a final answer using the supplied tool results. "
                        "Do not request another tool call."
                    ),
                ),
                (
                    "human",
                    (
                        "User query:\n{user_query}\n\n"
                        "Conversation history:\n{history_json}\n\n"
                        "Tool call results:\n{scratchpad_json}\n\n"
                        "Produce the final answer."
                    ),
                ),
            ]
        )

        decision_chain = decision_prompt | self.llm.with_structured_output(AgentDecision)
        final_response_chain = (
            final_response_prompt
            | self.llm.with_structured_output(AgentFinalResponse)
        )

        history_json = json.dumps(
            [block.content for block in context.blocks],
            default=str,
        )

        for _ in range(effective_max_tool_calls + 1):
            remaining_tool_calls = effective_max_tool_calls - budget.total_calls

            callable_tools = [
                tool
                for tool in allowed_tools
                if remaining_tool_calls > 0
                and budget.can_call(tool.name, tool_policy)
            ]

            scratchpad_json = json.dumps(scratchpad, default=str)

            # Once no call is available, the response-only schema makes another
            # tool call structurally impossible.
            if not callable_tools:
                raw_response = await final_response_chain.ainvoke(
                    {
                        "user_query": user_query,
                        "history_json": history_json,
                        "scratchpad_json": scratchpad_json,
                    }
                )
                response = (
                    AgentFinalResponse.model_validate(raw_response)
                    if isinstance(raw_response, dict)
                    else cast(AgentFinalResponse, raw_response)
                )

                return AgentRunResult(
                    answer=response.final_answer.strip() or "No answer generated.",
                    agent_name=self.agent_name,
                    model_name=self.llm.model_name,
                    finish_reason=OrchestrationFinishReason.COMPLETED,
                    tool_calls=tool_calls,
                )

            raw_decision = await decision_chain.ainvoke(
                {
                    "user_query": user_query,
                    "history_json": history_json,
                    "tools_json": json.dumps(
                        [asdict(tool) for tool in callable_tools],
                        default=str,
                    ),
                    "scratchpad_json": scratchpad_json,
                    "remaining_tool_calls": remaining_tool_calls,
                }
            )

            decision = (
                AgentDecision.model_validate(raw_decision)
                if isinstance(raw_decision, dict)
                else cast(AgentDecision, raw_decision)
            )

            if decision.action == "respond":
                return AgentRunResult(
                    answer=decision.final_answer.strip() or "No answer generated.",
                    agent_name=self.agent_name,
                    model_name=self.llm.model_name,
                    finish_reason=OrchestrationFinishReason.COMPLETED,
                    tool_calls=tool_calls,
                )

            tool_name = decision.tool_name
            callable_names = {tool.name for tool in callable_tools}

            if tool_name not in callable_names:
                if tool_policy.fail_on_policy_violation:
                    return AgentRunResult(
                        answer="Tool call blocked by policy.",
                        agent_name=self.agent_name,
                        model_name=self.llm.model_name,
                        finish_reason=OrchestrationFinishReason.POLICY_BLOCKED,
                        tool_calls=tool_calls,
                    )
                continue

            payload = decision.parse_tool_payload()
            tool_result = await tool_invoker(tool_name, payload)
            budget.mark_called(tool_name)

            # Keep tool_name in the trace wrapper, but remove its duplicate
            # from the nested result.
            sanitized_result = dict(tool_result)
            sanitized_result.pop("tool_name", None)

            tool_calls.append(
                ToolCallRecord(
                    tool_name=tool_name,
                    payload=dict(payload),
                    result=sanitized_result,
                )
            )

            scratchpad.append(
                {
                    "tool_name": tool_name,
                    "payload": payload,
                    "result": sanitized_result,
                }
            )

        return AgentRunResult(
            answer="Reached tool-call limit before final response.",
            agent_name=self.agent_name,
            model_name=self.llm.model_name,
            finish_reason=OrchestrationFinishReason.TOOL_LIMIT_REACHED,
            tool_calls=tool_calls,
        )
