import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import SessionFactory
from app.core.life_cycle import ManagedResource
from app.modules.assistant.application.facts.act_policy import FactAcceptancePolicy
from app.modules.assistant.application.ports import ConversationTurn
from app.modules.assistant.domain.facts import ExtractedFact, FactDecision, FactEvaluation
from app.modules.assistant.infrastructure.conversation_memory.long_term.fact_promoter import (
    FactPromotionResult,
)
from app.modules.assistant.infrastructure.conversation_memory.models import (
    AssistantConversationRecord,
    ConversationTurnRecord,
)
from app.modules.assistant.infrastructure.tool_gateway.models import AssistantToolAuditRecord


class FactExtractorPort(Protocol):
    async def extract(self, turns: list[tuple[UUID, ConversationTurn]]) -> list[ExtractedFact]: ...


class FactCandidateStorePort(Protocol):
    async def record_outcome(
        self,
        *,
        conversation_id: UUID,
        owner_user_id: UUID,
        fact: ExtractedFact,
        decision: FactDecision,
        reason: str,
    ) -> UUID: ...

    async def mark_promoted(self, candidate_id: UUID, memory_record_id: UUID) -> None: ...


class FactPromoterPort(Protocol):
    async def promote(
        self,
        fact: ExtractedFact,
        evaluation: FactEvaluation,
        *,
        owner_user_id: UUID,
        required_permissions: frozenset[str],
        source_turn_ids: tuple[UUID, ...],
        now: datetime,
    ) -> FactPromotionResult: ...


@dataclass(slots=True)
class ConsolidationWorker(ManagedResource):
    session_factory: SessionFactory
    fact_extractor: FactExtractorPort
    fact_policy: FactAcceptancePolicy
    candidate_store: FactCandidateStorePort
    fact_promoter: FactPromoterPort
    tool_permissions_by_name: dict[str, str]
    idle_minutes: int
    poll_interval_seconds: float = 30.0
    batch_size: int = 20
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event, init=False, repr=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="conversation-consolidation-worker")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def consolidate_once(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(minutes=self.idle_minutes)
        processed = 0

        async with self.session_factory() as session:
            statement = (
                select(AssistantConversationRecord)
                .where(AssistantConversationRecord.consolidated_at.is_(None))
                .where(AssistantConversationRecord.last_turn_at <= cutoff)
                .where(AssistantConversationRecord.turn_count >= 2)
                .order_by(AssistantConversationRecord.last_turn_at.asc())
                .limit(self.batch_size)
                .with_for_update(skip_locked=True)
            )
            conversations = list((await session.scalars(statement)).all())

            for conversation in conversations:
                turns = list(
                    (
                        await session.scalars(
                            select(ConversationTurnRecord)
                            .where(ConversationTurnRecord.conversation_id == conversation.id)
                            .order_by(
                                ConversationTurnRecord.created_at.asc(),
                                ConversationTurnRecord.id.asc(),
                            )
                        )
                    ).all()
                )
                if len(turns) < 2 or conversation.owner_user_id is None:
                    conversation.consolidated_at = datetime.now(UTC)
                    processed += 1
                    continue

                conversation_turns = [
                    (
                        turn.id,
                        ConversationTurn(
                            role=turn.role,
                            content=turn.content,
                            created_at_utc=turn.created_at,
                        ),
                    )
                    for turn in turns
                ]
                facts = await self.fact_extractor.extract(conversation_turns)
                required_permissions = await self._required_permissions_for_conversation(
                    session=session,
                    conversation_id=conversation.id,
                )
                source_turn_ids = tuple(turn.id for turn in turns)
                source_turn_id_set = frozenset(source_turn_ids)
                now = datetime.now(UTC)

                for fact in facts:
                    evaluation = self.fact_policy.evaluate(fact, source_turn_id_set, now)
                    candidate_id = await self.candidate_store.record_outcome(
                        conversation_id=conversation.id,
                        owner_user_id=conversation.owner_user_id,
                        fact=fact,
                        decision=evaluation.decision,
                        reason=evaluation.reason,
                    )
                    if evaluation.decision.value != "accepted":
                        continue
                    promotion = await self.fact_promoter.promote(
                        fact,
                        evaluation,
                        owner_user_id=conversation.owner_user_id,
                        required_permissions=required_permissions,
                        source_turn_ids=source_turn_ids,
                        now=now,
                    )
                    await self.candidate_store.mark_promoted(
                        candidate_id, promotion.memory_record_id
                    )

                conversation.consolidated_at = datetime.now(UTC)
                processed += 1

            await session.commit()

        return processed

    async def _required_permissions_for_conversation(
        self,
        *,
        session: AsyncSession,
        conversation_id: UUID,
    ) -> frozenset[str]:
        rows = list(
            (
                await session.scalars(
                    select(AssistantToolAuditRecord)
                    .where(AssistantToolAuditRecord.conversation_id == conversation_id)
                    .where(AssistantToolAuditRecord.decision == "approved")
                )
            ).all()
        )
        return frozenset(
            permission
            for row in rows
            for permission in [self.tool_permissions_by_name.get(row.tool_name)]
            if permission is not None
        )

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            if await self.consolidate_once() == 0:
                await asyncio.sleep(self.poll_interval_seconds)
