import json
from dataclasses import asdict, dataclass
from typing import Any, cast
from uuid import UUID

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.modules.assistant.application.ports import (
    AgentOrchestratorPort,
    ToolInvoker,
)
from app.modules.assistant.domain.context import AssembledContext
from app.modules.assistant.domain.entities import (
    AgentRunResult,
    ToolCallRecord,
    ToolDescriptor,
    ToolOutcomeStatus,
)
from app.modules.assistant.domain.tool_call import ToolCallBudgetState, ToolCallPolicy
from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from app.modules.assistant.infrastructure.agents.structured_decision import (
    MIN_TOOL_DECISION_CONFIDENCE,
    AgentDecision,
    AgentFinalResponse,
)


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
            min(max(max_tool_calls, 0), tool_policy.max_total_calls) if allow_tool_calls else 0
        )

        allowed_tools = [
            tool for tool in available_tools if tool.name in tool_policy.allowed_tool_names
        ]

        decision_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are an orchestration agent. "
                        "Use only the provided tools. "
                        "Treat each tool description and input schema as a strict contract. "
                        "Use a tool only when it directly supports the requested outcome. "
                        "Never use an internal ERP tool for definitions or explanations. "
                        "Never invent site codes, statuses, identifiers, or write intent. "
                        "Mutating tools require an explicit user request for that mutation. "
                        "If no tool is needed or confidence is low, respond directly. "
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
                        "Return an intent, confidence from 0 to 1, and a brief internal rationale. "
                        "For action=tool_call: final_answer must be null, tool_name must exactly "
                        "match a callable tool, and tool_payload_json must be a JSON object string "
                        "containing only supported fields explicitly grounded in the request. "
                        "For action=respond: final_answer must be non-empty and both tool fields "
                        "must be null. Never include the rationale in final_answer."
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
                        "Answer the user's requested outcome using only facts in the supplied "
                        "tool results. Never replace successful ERP results with a definition "
                        "or unrelated explanation. For collection requests, state the actual "
                        "count and enumerate only returned records. If fewer records were "
                        "returned than requested, say so. Never invent missing records. "
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

        decision_chain = decision_prompt | self.llm.with_structured_output(
            AgentDecision,
            method="function_calling",
        )
        final_response_chain = final_response_prompt | self.llm.with_structured_output(
            AgentFinalResponse,
            method="function_calling",
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
                if remaining_tool_calls > 0 and budget.can_call(tool.name, tool_policy)
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
                    # dummy evidence temporarily
                    evidence=[],  # type: ignore
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
                    answer=decision.response_text().strip() or "No answer generated.",
                    agent_name=self.agent_name,
                    model_name=self.llm.model_name,
                    finish_reason=OrchestrationFinishReason.COMPLETED,
                    tool_calls=tool_calls,
                    evidence=[],  # type: ignore
                )

            if decision.confidence < MIN_TOOL_DECISION_CONFIDENCE:
                return AgentRunResult(
                    answer="I need more information before I can safely select a tool.",
                    agent_name=self.agent_name,
                    model_name=self.llm.model_name,
                    finish_reason=OrchestrationFinishReason.COMPLETED,
                    tool_calls=tool_calls,
                    evidence=[],  # type: ignore
                )

            tool_name, payload = decision.tool_call()
            callable_names = {tool.name for tool in callable_tools}

            if tool_name not in callable_names:
                if tool_policy.fail_on_policy_violation:
                    return AgentRunResult(
                        answer="Tool call blocked by policy.",
                        agent_name=self.agent_name,
                        model_name=self.llm.model_name,
                        finish_reason=OrchestrationFinishReason.POLICY_BLOCKED,
                        tool_calls=tool_calls,
                        evidence=[],  # type: ignore
                    )
                continue

            budget.mark_called(tool_name)

            tool_calls.append(
                ToolCallRecord(
                    tool_name=tool_name,
                    payload=dict(payload),
                    result={},
                    # temporarily dummy status and evidence
                    status=ToolOutcomeStatus.SUCCESS,
                    evidence=[],  # type: ignore
                )
            )

            scratchpad.append(
                {
                    "tool_name": tool_name,
                    "payload": payload,
                    "result": {},
                }
            )

        return AgentRunResult(
            answer="Reached tool-call limit before final response.",
            agent_name=self.agent_name,
            model_name=self.llm.model_name,
            finish_reason=OrchestrationFinishReason.TOOL_LIMIT_REACHED,
            tool_calls=tool_calls,
            evidence=[],  # type: ignore
        )
