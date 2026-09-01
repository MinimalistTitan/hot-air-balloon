from app.shared.domain.errors import DomainError


class AssistantOrchestrationFailedError(DomainError):
    code = "assistant_orchestration_failed"


class AssistantToolInvocationError(DomainError):
    code = "assistant_tool_invocation_failed"


class ConversationOwnershipError(DomainError):
    """The requested conversation is absent or belongs to another user."""

    code = "assistant_conversation_not_found"

    def __init__(self) -> None:
        super().__init__("The requested conversation was not found.")
