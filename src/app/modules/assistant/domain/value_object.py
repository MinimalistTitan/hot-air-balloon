from enum import StrEnum


class OrchestrationFinishReason(StrEnum):
    COMPLETED = "completed"
    TOOL_LIMIT_REACHED = "tool_limit_reached"
    POLICY_BLOCKED = "policy_blocked"
    FAILED = "failed"