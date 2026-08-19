from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.assistant.domain.entities import AgentRunResult, ToolDescriptor
from app.modules.assistant.domain.tool_call import ToolCallPolicy
from app.modules.user.domain.authorization import AuthorizationContext

ToolInvoker = Callable[[str, dict[str, object]], Awaitable[dict[str, object]]]

@dataclass(frozen=True, slots=True)
class ConversationTurn:
    role: str
    content: str
    created_at_utc: datetime

class ToolRuntimePort(Protocol):
    async def list_tools(self) -> list[ToolDescriptor]: ...
    async def invoke(
        self,
        tool_name: str,
        payload: dict[str, object],
        authorization_context: AuthorizationContext,
    ) -> dict[str, object]: ...
    
class AgentOrchestratorPort(Protocol):
    async def run(
        self,
        conversation_id: UUID,
        user_query: str,
        available_tools: list[ToolDescriptor],
        tool_invoker: ToolInvoker,
        conversation_history: list[ConversationTurn],
        tool_policy: ToolCallPolicy,
        max_tool_calls: int,
        allow_tool_calls: bool,
    ) -> AgentRunResult: ...
    
class AssistantTelemetryPort(Protocol):
    def query_started(self, query: str) -> None: ...
    def tool_called(self, tool_name: str) -> None: ...
    def query_completed(self, tools_used: int) -> None: ...
    
class ConversationStorePort(Protocol):
    async def read_recent(self, conversation_id: UUID, limit: int = 12) -> list[ConversationTurn]: ...
    async def append(self, conversation_id: UUID, turn: ConversationTurn) -> None: ...