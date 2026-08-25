from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database.database import Base, create_session_factory
from app.modules.assistant.application.context.providers import ContextRequest
from app.modules.assistant.application.context.user_memory_provider import UserMemoryProvider
from app.modules.assistant.application.facts.act_policy import FactAcceptancePolicy
from app.modules.assistant.application.ports import ConversationTurn, MemoryRecordWrite
from app.modules.assistant.domain.context import ContextKind
from app.modules.assistant.domain.facts import (
    ExtractedFact,
    FactClass,
    FactDecision,
    FactEvaluation,
)
from app.modules.assistant.infrastructure.context.tiktoken_counter import TiktokenCounter
from app.modules.assistant.infrastructure.conversation_memory.long_term.consolidation_worker import (
    ConsolidationWorker,
)
from app.modules.assistant.infrastructure.conversation_memory.long_term.fact_promoter import (
    FactPromotionResult,
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


class FakeFactExtractor:
    async def extract(
        self,
        turns: list[tuple[UUID, ConversationTurn]],
    ) -> list[ExtractedFact]:
        assert len(turns) == 2
        return [
            ExtractedFact(
                statement="User prefers daily maintenance summaries.",
                fact_class=FactClass.PREFERENCE,
                evidence_turn_ids=(turns[0][0],),
                entity_refs=(),
                explicitly_stated=True,
            )
        ]


class FakeCandidateStore:
    def __init__(self) -> None:
        self.outcomes: list[FactDecision] = []
        self.promoted: list[UUID] = []

    async def record_outcome(
        self,
        *,
        conversation_id: UUID,
        owner_user_id: UUID,
        fact: ExtractedFact,
        decision: FactDecision,
        reason: str,
    ) -> UUID:
        del conversation_id, owner_user_id, fact, reason
        self.outcomes.append(decision)
        return uuid4()

    async def mark_promoted(self, candidate_id: UUID, memory_record_id: UUID) -> None:
        del candidate_id
        self.promoted.append(memory_record_id)


class FakeFactPromoter:
    async def promote(
        self,
        fact: ExtractedFact,
        evaluation: FactEvaluation,
        *,
        owner_user_id: UUID,
        required_permissions: frozenset[str],
        source_turn_ids: tuple[UUID, ...],
        now: datetime,
    ) -> FactPromotionResult:
        del fact, evaluation, owner_user_id, required_permissions, source_turn_ids, now
        return FactPromotionResult(memory_record_id=uuid4(), decision=FactDecision.ACCEPTED)


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

    candidate_store = FakeCandidateStore()
    worker = ConsolidationWorker(
        session_factory=session_factory,
        fact_extractor=FakeFactExtractor(),
        fact_policy=FactAcceptancePolicy(
            max_statement_characters=500, rederivable_terms=frozenset()
        ),
        candidate_store=candidate_store,
        fact_promoter=FakeFactPromoter(),
        tool_permissions_by_name={"get_work_orders": "work_orders:read"},
        idle_minutes=30,
        batch_size=10,
    )

    assert await worker.consolidate_once() == 1
    assert candidate_store.outcomes == [FactDecision.ACCEPTED]
    assert len(candidate_store.promoted) == 1

    async with session_factory() as session:
        conversation = await session.scalar(
            select(AssistantConversationRecord).where(
                AssistantConversationRecord.id == conversation_id
            )
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
