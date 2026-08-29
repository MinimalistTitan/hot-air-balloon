import structlog

from app.modules.assistant.application.ports import AssistantTelemetryPort
from app.modules.assistant.domain.entities import AssistantDecisionEvent


class StructlogAssistantTelemetry(AssistantTelemetryPort):
    def __init__(self) -> None:
        self._logger = structlog.get_logger("assistant.orchestration")

    def query_started(self, query: str) -> None:
        self._logger.info("assistant_query_started", query_preview=query[:120])

    def tool_called(self, tool_name: str) -> None:
        self._logger.info("assistant_tool_called", tool_name=tool_name)

    def decision_recorded(self, event: AssistantDecisionEvent) -> None:
        self._logger.info(
            "assistant_decision_recorded",
            conversation_id=str(event.conversation_id) if event.conversation_id else None,
            stage=event.stage.value,
            outcome=event.outcome.value,
            source=event.source,
            intent=event.intent,
            confidence=event.confidence,
            action=event.action,
            tool_name=event.tool_name,
            reason_code=event.reason_code,
            callable_tool_count=event.callable_tool_count,
        )

    def query_completed(self, tools_used: int) -> None:
        self._logger.info("assistant_query_completed", tools_used=tools_used)
