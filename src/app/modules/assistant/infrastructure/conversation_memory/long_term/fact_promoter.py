from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.assistant.application.ports import MemoryRecordWrite
from app.modules.assistant.domain.facts import ExtractedFact, FactDecision, FactEvaluation
from app.modules.assistant.infrastructure.conversation_memory.long_term.memory_record_repository import (
    MemoryRecordRepository,
)


@dataclass(frozen=True, slots=True)
class FactPromotionResult:
    memory_record_id: UUID
    decision: FactDecision


@dataclass(slots=True)
class FactPromoter:
    memory_store: MemoryRecordRepository

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
        del now
        memory_record_id, created = await self.memory_store.record_or_get_user_fact(
            MemoryRecordWrite(
                kind="conversation_summary",
                content=fact.statement,
                owner_user_id=owner_user_id,
                site_code=None,
                required_permissions=required_permissions,
                source_turn_ids=source_turn_ids,
                expires_at_utc=evaluation.expires_at_utc,
            )
        )
        return FactPromotionResult(
            memory_record_id=memory_record_id,
            decision=FactDecision.ACCEPTED if created else FactDecision.DUPLICATE,
        )
