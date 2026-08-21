from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database.database import Base, create_session_factory
from app.modules.assistant.application.context.providers import ContextRequest
from app.modules.assistant.application.context.user_memory_provider import UserMemoryProvider
from app.modules.assistant.application.ports import ConversationTurn, MemoryRecordWrite
from app.modules.assistant.domain.context import ContextKind
from app.modules.assistant.infrastructure.context.tiktoken_counter import TiktokenCounter
from app.modules.assistant.infrastructure.conversation_memory.long_term.consolidation_worker import (
    ConsolidationWorker,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.llm_summarizer import (
    ConversationSummary,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.memory_record_repository import (
    MemoryRecordRepository,
)
from app.modules.assistant.infrastructure.conversation_memory.models import (
    AssistantConversationRecord,
    ConversationTurnRecord,
)
from app.modules.assistant.infrastructure.tool_gateway.models import AssistantToolAuditRecord
from app.modules.user.domain.authorization import AuthorizationContext, RoleName


class FakeSummarizer:
    async def summarize(self, turns: list[ConversationTurn]) -> ConversationSummary:
        assert len(turns) == 2
        return ConversationSummary(
            summary="User likes daily updates.",
            salient_facts=[
                "User prefers daily maintenance summaries.",
                "User asks for concise status updates.",
            ],
        )


class FakeMemoryStore:
    def __init__(self) -> None:
        self.writes: list[MemoryRecordWrite] = []

    async def record(self, memory: MemoryRecordWrite) -> UUID:
        self.writes.append(memory)
        return uuid4()


async def test_consolidation_worker_writes_fact_records_and_marks_conversation() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    conversation_id = uuid4()
    owner_user_id = uuid4()
    now = datetime.now(UTC)
    old_turn_time = now - timedelta(minutes=90)
    first_turn_id = uuid4()
    second_turn_id = uuid4()

    async with session_factory() as session:
        session.add(
            AssistantConversationRecord(
                id=conversation_id,
                owner_user_id=owner_user_id,
                started_at=old_turn_time,
                last_turn_at=old_turn_time,
                turn_count=2,
                consolidated_at=None,
                closed_at=None,
            )
        )
        session.add_all(
            [
                ConversationTurnRecord(
                    id=first_turn_id,
                    conversation_id=conversation_id,
                    owner_user_id=owner_user_id,
                    role="user",
                    content="Need daily updates",
                    created_at=old_turn_time,
                    expires_at=None,
                ),
                ConversationTurnRecord(
                    id=second_turn_id,
                    conversation_id=conversation_id,
                    owner_user_id=owner_user_id,
                    role="assistant",
                    content="Will send concise daily updates",
                    created_at=old_turn_time + timedelta(seconds=1),
                    expires_at=None,
                ),
            ]
        )
        session.add(
            AssistantToolAuditRecord(
                tool_name="get_work_orders",
                actor=str(owner_user_id),
                conversation_id=conversation_id,
                payload_json={},
                decision="approved",
                reason=None,
                created_at_utc=old_turn_time,
            )
        )
        await session.commit()

    memory_store = FakeMemoryStore()
    worker = ConsolidationWorker(
        session_factory=session_factory,
        summarizer=FakeSummarizer(),
        memory_store=memory_store,
        tool_permissions_by_name={"get_work_orders": "work_orders:read"},
        idle_minutes=30,
        summary_retention_days=180,
        batch_size=10,
    )

    assert await worker.consolidate_once() == 1
    assert len(memory_store.writes) == 2
    assert all(write.kind == "conversation_summary" for write in memory_store.writes)
    assert all(write.owner_user_id == owner_user_id for write in memory_store.writes)
    assert all(write.required_permissions == frozenset({"work_orders:read"}) for write in memory_store.writes)
    assert all(write.source_turn_ids == (first_turn_id, second_turn_id) for write in memory_store.writes)

    async with session_factory() as session:
        conversation = await session.scalar(
            select(AssistantConversationRecord).where(AssistantConversationRecord.id == conversation_id)
        )

    assert conversation is not None
    assert conversation.consolidated_at is not None
    await engine.dispose()


async def test_user_memory_provider_returns_user_memory_blocks() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    repository = MemoryRecordRepository(
        session_factory=session_factory,
        embedding_model="text-embedding-3-small",
        user_memory_namespace="user-memory",
        documents_namespace="documents",
    )
    owner_user_id = uuid4()
    await repository.record(
        MemoryRecordWrite(
            kind="conversation_summary",
            content="User prefers concise daily summaries.",
            owner_user_id=owner_user_id,
            site_code=None,
            required_permissions=frozenset(),
        )
    )

    provider = UserMemoryProvider(
        memory_reader=repository,
        counter=TiktokenCounter(),
        limit=5,
    )
    blocks = await provider.get_blocks(
        ContextRequest(
            conversation_id=uuid4(),
            user_query="What do I usually ask for?",
            authorization_context=AuthorizationContext(
                user_id=owner_user_id,
                roles=frozenset({RoleName.READ_ONLY_ANALYST}),
            ),
        )
    )

    assert len(blocks) == 1
    assert blocks[0].kind is ContextKind.USER_MEMORY
    assert "concise daily summaries" in blocks[0].content
    await engine.dispose()
