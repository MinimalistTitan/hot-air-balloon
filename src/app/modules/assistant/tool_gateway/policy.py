from __future__ import annotations

from app.modules.assistant.tool_gateway.domain import ToolApprovalDecision


class PolicyApprovalService:
    def __init__(self, *, allow_write_tools: bool = False) -> None:
        self._allow_write_tools = allow_write_tools

    async def evaluate(
        self,
        *,
        tool_name: str,
        actor: str | None,
        payload: dict[str, object],
    ) -> ToolApprovalDecision:
        if (
            tool_name.startswith("write_") or tool_name.endswith("_write")
        ) and not self._allow_write_tools:
            return ToolApprovalDecision.APPROVAL_REQUIRED

        return ToolApprovalDecision.APPROVED