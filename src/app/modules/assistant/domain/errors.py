from app.shared.domain.errors import DomainError


class AssistantOrchestrationFailedError(DomainError):
    code = "assistant_orchestration_failed"


class AssistantToolInvocationError(DomainError):
    code = "assistant_tool_invocation_failed"