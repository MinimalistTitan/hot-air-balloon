from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.modules.assistant.application.ports import ToolInvoker
from app.modules.assistant.application.response_composer import FinalResponseComposer
from app.modules.assistant.domain.entities import AssistantDecisionEvent
from app.modules.assistant.infrastructure.agents.langgraph.contracts import AgentBrain

DecisionObserver = Callable[[AssistantDecisionEvent], None]


@dataclass(frozen=True, slots=True)
class GraphContext:
    brain: AgentBrain
    tool_invoker: ToolInvoker
    response_composer: FinalResponseComposer
    conversation_id: UUID | None = None
    decision_observer: DecisionObserver | None = None

    def record_decision(self, event: AssistantDecisionEvent) -> None:
        if self.decision_observer is None:
            return
        try:
            self.decision_observer(event)
        except Exception:
            # Telemetry must never alter orchestration behavior.
            return
