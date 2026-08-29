from dataclasses import dataclass, field
from typing import Any, Protocol, cast
from uuid import UUID

from langchain_core.runnables.config import RunnableConfig

from app.modules.assistant.application.ports import (
    AgentOrchestratorPort,
    ToolInvoker,
)
from app.modules.assistant.application.response_composer import FinalResponseComposer
from app.modules.assistant.domain.context import AssembledContext
from app.modules.assistant.domain.entities import AgentRunResult, ToolDescriptor
from app.modules.assistant.domain.tool_call import ToolCallPolicy
from app.modules.assistant.domain.value_object import OrchestrationFinishReason
from app.modules.assistant.infrastructure.agents.langgraph.context import (
    DecisionObserver,
    GraphContext,
)
from app.modules.assistant.infrastructure.agents.langgraph.contracts import AgentBrain
from app.modules.assistant.infrastructure.agents.langgraph.state import GraphState
from app.modules.assistant.infrastructure.agents.langgraph.workflow import build_workflow
from langgraph.checkpoint.base import BaseCheckpointSaver


class CompiledWorkflow(Protocol):
    async def ainvoke(
        self,
        input: GraphState,
        config: RunnableConfig | None = None,
        *,
        context: GraphContext | None = None,
    ) -> object: ...

@dataclass(slots=True)
class LangGraphAgentOrchestrator(AgentOrchestratorPort):
    brain: AgentBrain
    model_name: str
    response_composer: FinalResponseComposer = field(default_factory=FinalResponseComposer)
    agent_name: str = "assistant.langgraph"
    checkpointer: BaseCheckpointSaver[Any] | None = None
    decision_observer: DecisionObserver | None = None
    _workflow: CompiledWorkflow = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self._workflow = cast(CompiledWorkflow, build_workflow(self.checkpointer))

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
        effective_max_tool_calls = (
            min(max(max_tool_calls, 0), tool_policy.max_total_calls) if allow_tool_calls else 0
        )
        allowed_tools = [
            tool for tool in available_tools if tool.name in tool_policy.allowed_tool_names
        ]
        initial_state: GraphState = {
            "user_query": user_query,
            "context_prompt": context.render(),
            "available_tools": allowed_tools,
            "conversation_history": [],
            "intent": "",
            "planned_action": {"action": "respond", "tool_name": "", "payload": {}},
            "pending_call": None,
            "tool_calls": [],
            "total_tool_calls": 0,
            "per_tool_calls": {},
            "remaining_tool_calls": effective_max_tool_calls,
            "max_calls_per_tool": tool_policy.max_calls_per_tool,
            "next_step": "respond",
            "answer": "",
            "finish_reason": None,
        }

        configuration = cast(
            RunnableConfig,
            {"configurable": {"thread_id": str(conversation_id)}},
        )

        raw_result = await self._workflow.ainvoke(
            initial_state,
            config=configuration,
            context=GraphContext(
                brain=self.brain,
                tool_invoker=tool_invoker,
                response_composer=self.response_composer,
                conversation_id=conversation_id,
                decision_observer=self.decision_observer,
            ),
        )

        result = cast(GraphState, raw_result)

        finish_reason = result["finish_reason"] or OrchestrationFinishReason.FAILED

        tool_calls = result["tool_calls"]
        evidence = tuple(
            block
            for tool_call in tool_calls
            for block in tool_call.evidence
        )

        return AgentRunResult(
            answer=result["answer"] or "No answer generated.",
            agent_name=self.agent_name,
            model_name=self.model_name,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            evidence=evidence,
        )
