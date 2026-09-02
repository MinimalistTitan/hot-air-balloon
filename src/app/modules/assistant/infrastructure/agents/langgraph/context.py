from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from uuid import UUID

from app.modules.assistant.application.ports import ConversationTurn, ToolInvoker
from app.modules.assistant.application.response_composer import FinalResponseComposer
from app.modules.assistant.domain.context import AssembledContext
from app.modules.assistant.domain.entities import AssistantDecisionEvent, ToolDescriptor
from app.modules.assistant.infrastructure.agents.langgraph.contracts import AgentBrain
from app.modules.assistant.infrastructure.agents.langgraph.state import (
    AgentStateView,
    GraphState,
)
from app.modules.user.domain.authorization import AuthorizationContext

DecisionObserver = Callable[[AssistantDecisionEvent], None]


@dataclass(slots=True)
class ToolCallBudget:
    remaining_calls: int
    max_calls_per_tool: int
    total_calls: int = 0
    per_tool_calls: dict[str, int] = field(default_factory=dict)

    def can_call(self, tool_name: str) -> bool:
        return (
            self.remaining_calls > 0
            and self.per_tool_calls.get(tool_name, 0) < self.max_calls_per_tool
        )

    def record(self, tool_name: str) -> None:
        if not self.can_call(tool_name):
            raise RuntimeError("Tool-call budget was exhausted before recording the result")
        self.total_calls += 1
        self.remaining_calls -= 1
        self.per_tool_calls[tool_name] = self.per_tool_calls.get(tool_name, 0) + 1


@dataclass(frozen=True, slots=True)
class GraphContext:
    brain: AgentBrain
    authorization_context: AuthorizationContext
    available_tools: tuple[ToolDescriptor, ...]
    tool_invoker: ToolInvoker
    call_budget: ToolCallBudget
    retrieved_context: AssembledContext
    user_query: str
    conversation_history: tuple[ConversationTurn, ...] = ()
    response_composer: FinalResponseComposer = field(default_factory=FinalResponseComposer)
    conversation_id: UUID | None = None
    decision_observer: DecisionObserver | None = None

    def agent_state(
        self,
        state: GraphState,
        *,
        available_tools: Sequence[ToolDescriptor] | None = None,
    ) -> AgentStateView:
        return {
            "user_query": self.user_query,
            "context_prompt": self.retrieved_context.render(),
            "available_tools": list(
                self.available_tools if available_tools is None else available_tools
            ),
            "conversation_history": list(self.conversation_history),
            "intent": state["intent"],
            "planned_action": state["planned_action"],
            "pending_call": state["pending_call"],
            "tool_calls": state["tool_calls"],
            "total_tool_calls": self.call_budget.total_calls,
            "per_tool_calls": dict(self.call_budget.per_tool_calls),
            "remaining_tool_calls": self.call_budget.remaining_calls,
            "max_calls_per_tool": self.call_budget.max_calls_per_tool,
            "next_step": state["next_step"],
            "answer": state["answer"],
            "finish_reason": state["finish_reason"],
        }

    def record_decision(self, event: AssistantDecisionEvent) -> None:
        if self.decision_observer is None:
            return
        try:
            self.decision_observer(event)
        except Exception:
            # Telemetry must never alter orchestration behavior.
            return
