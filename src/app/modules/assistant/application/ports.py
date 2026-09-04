from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from app.modules.assistant.domain.context import AssembledContext
from app.modules.assistant.domain.conversation_evidence import ConversationEvidenceSnapshot
from app.modules.assistant.domain.entities import (
    AgentRunResult,
    AssistantDecisionEvent,
    ToolCallRecord,
    ToolDescriptor,
)
from app.modules.assistant.domain.tool_call import ToolCallPolicy
from app.modules.user.domain.authorization import AuthorizationContext

if TYPE_CHECKING:
    from app.modules.assistant.application.context.providers import ContextRequest

ToolInvoker = Callable[[str, dict[str, object]], Awaitable[ToolCallRecord]]


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    role: str
    content: str
    created_at_utc: datetime


@dataclass(frozen=True, slots=True)
class MemoryRecordWrite:
    kind: str
    content: str
    owner_user_id: UUID | None
    site_code: str | None
    required_permissions: frozenset[str]
    source_turn_ids: tuple[UUID, ...] = ()
    source_document_id: UUID | None = None
    expires_at_utc: datetime | None = None


@dataclass(frozen=True, slots=True)
class VectorRecord:
    vector_id: str
    values: list[float]
    metadata: dict[str, str | int | list[str] | None]


@dataclass(frozen=True, slots=True)
class EraseUserMemoryResult:
    deleted_memory_records: int
    deleted_vectors: int
    deleted_turns: int
    deleted_conversations: int


class TokenCounterPort(Protocol):
    def count(self, text: str) -> int: ...


class ContextAssemblerPort(Protocol):
    async def assemble(self, request: ContextRequest) -> AssembledContext: ...


class ToolRuntimePort(Protocol):
    async def list_tools(
        self,
        authorization_context: AuthorizationContext,
    ) -> list[ToolDescriptor]: ...
    async def invoke(
        self,
        tool_name: str,
        payload: dict[str, object],
        authorization_context: AuthorizationContext,
        conversation_id: UUID | None = None,
    ) -> ToolCallRecord: ...


class AgentOrchestratorPort(Protocol):
    async def run(
        self,
        conversation_id: UUID,
        authorization_context: AuthorizationContext,
        user_query: str,
        available_tools: list[ToolDescriptor],
        tool_invoker: ToolInvoker,
        context: AssembledContext,
        tool_policy: ToolCallPolicy,
        max_tool_calls: int,
        allow_tool_calls: bool,
    ) -> AgentRunResult: ...


class AssistantTelemetryPort(Protocol):
    def query_started(self, query: str) -> None: ...
    def tool_called(self, tool_name: str) -> None: ...
    def decision_recorded(self, event: AssistantDecisionEvent) -> None: ...
    def query_completed(self, tools_used: int) -> None: ...


class MemoryWriterPort(Protocol):
    async def record_turn(
        self,
        conversation_id: UUID,
        turn: ConversationTurn,
        owner_user_id: UUID,
    ) -> None: ...

    async def close_conversation(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
    ) -> None: ...


class EmbeddingPort(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class VectorIndexPort(Protocol):
    async def upsert(self, namespace: str, records: list[VectorRecord]) -> None: ...

    async def query_ids(
        self,
        namespace: str,
        values: list[float],
        limit: int,
        metadata_filter: dict[str, str],
    ) -> list[str]: ...

    async def fetch_ids(self, namespace: str, vector_ids: list[str]) -> set[str]: ...

    async def list_ids(self, namespace: str) -> set[str]: ...

    async def delete_ids(self, namespace: str, vector_ids: list[str]) -> None: ...


class LongTermMemoryPort(Protocol):
    async def record(self, memory: MemoryRecordWrite) -> UUID: ...


class UserMemoryReaderPort(Protocol):
    async def read_recent_user_memories(self, owner_user_id: UUID, limit: int) -> list[str]: ...


class DocumentMemoryReaderPort(Protocol):
    async def read_document_chunks(
        self,
        query: str,
        authorization_context: AuthorizationContext,
        limit: int,
    ) -> list[str]: ...


class UserMemoryErasePort(Protocol):
    async def erase_user_memory(self, owner_user_id: UUID) -> EraseUserMemoryResult: ...


class CheckpointErasePort(Protocol):
    async def erase_conversation(
        self,
        owner_user_id: UUID,
        conversation_id: UUID,
    ) -> None: ...


class ConversationStorePort(Protocol):
    async def claim_or_validate(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
        observed_at_utc: datetime,
    ) -> None: ...

    async def read_recent(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
        limit: int = 12,
    ) -> list[ConversationTurn]: ...

    async def append(
        self,
        conversation_id: UUID,
        turn: ConversationTurn,
        owner_user_id: UUID,
    ) -> None: ...

    async def append_completed_exchange(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
        user_turn: ConversationTurn,
        assistant_turn: ConversationTurn,
        evidence: ConversationEvidenceSnapshot | None = None,
    ) -> None: ...

    async def read_recent_evidence(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
        limit: int = 12,
    ) -> list[ConversationEvidenceSnapshot]: ...

    async def erase_evidence(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
    ) -> int: ...


class ConversationEvidenceStorePort(Protocol):
    async def append_evidence(
        self,
        snapshot: ConversationEvidenceSnapshot,
    ) -> None: ...

    async def read_recent_evidence(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
        limit: int = 12,
    ) -> list[ConversationEvidenceSnapshot]: ...

    async def erase_evidence(
        self,
        conversation_id: UUID,
        owner_user_id: UUID,
    ) -> int: ...
