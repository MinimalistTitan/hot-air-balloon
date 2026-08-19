import structlog

from app.modules.assistant.application.ports import AssistantTelemetryPort


class StructlogAssistantTelemetry(AssistantTelemetryPort):
    def __init__(self) -> None:
        self._logger = structlog.get_logger("assistant.orchestration")

    def query_started(self, query: str) -> None:
        self._logger.info("assistant_query_started", query_preview=query[:120])

    def tool_called(self, tool_name: str) -> None:
        self._logger.info("assistant_tool_called", tool_name=tool_name)

    def query_completed(self, tools_used: int) -> None:
        self._logger.info("assistant_query_completed", tools_used=tools_used)