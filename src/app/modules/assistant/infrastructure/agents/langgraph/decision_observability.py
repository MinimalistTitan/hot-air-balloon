from app.modules.assistant.domain.entities import (
    AssistantDecisionEvent,
    DecisionOutcome,
    DecisionStage,
)
from app.modules.assistant.infrastructure.agents.langgraph.context import GraphContext


def record_decision(
    context: GraphContext,
    *,
    stage: DecisionStage,
    outcome: DecisionOutcome,
    source: str,
    intent: str | None = None,
    confidence: float | None = None,
    action: str | None = None,
    tool_name: str | None = None,
    reason_code: str | None = None,
    callable_tool_count: int | None = None,
) -> None:
    """Emit only bounded decision metadata; never queries, payloads, results, or rationale."""

    recorder = getattr(context, "record_decision", None)
    if not callable(recorder):
        return
    recorder(
        AssistantDecisionEvent(
            conversation_id=getattr(context, "conversation_id", None),
            stage=stage,
            outcome=outcome,
            source=source,
            intent=intent,
            confidence=confidence,
            action=action,
            tool_name=tool_name,
            reason_code=reason_code,
            callable_tool_count=callable_tool_count,
        )
    )
