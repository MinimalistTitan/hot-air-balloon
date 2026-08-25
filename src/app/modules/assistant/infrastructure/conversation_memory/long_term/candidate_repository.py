from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from app.core.database.database import SessionFactory
from app.modules.assistant.domain.facts import ExtractedFact, FactDecision
from app.modules.assistant.infrastructure.conversation_memory.long_term.models import (
    AssistantMemoryCandidate,
)


@dataclass(slots=True)
class FactCandidateRepository:
    session_factory: SessionFactory
    retention_days: int

    async def record_outcome(
        self,
        *,
        conversation_id: UUID,
        owner_user_id: UUID,
        fact: ExtractedFact,
        decision: FactDecision,
        reason: str,
    ) -> UUID:
        candidate_id = uuid4()
        now = datetime.now(UTC)
        async with self.session_factory() as session:
            session.add(
                AssistantMemoryCandidate(
                    id=candidate_id,
                    conversation_id=conversation_id,
                    owner_user_id=owner_user_id,
                    statement=fact.statement,
                    statement_sha256=sha256(fact.statement.strip().lower().encode()).hexdigest(),
                    fact_class=fact.fact_class.value,
                    entity_refs=list(fact.entity_refs),
                    evidence_turn_ids=list(fact.evidence_turn_ids),
                    explicitly_stated=fact.explicitly_stated,
                    decision=decision.value,
                    decision_reason=reason,
                    promoted_memory_record_id=None,
                    created_at=now,
                    expires_at=now + timedelta(days=self.retention_days),
                )
            )
            await session.commit()
        return candidate_id

    async def mark_promoted(self, candidate_id: UUID, memory_record_id: UUID) -> None:
        async with self.session_factory() as session:
            candidate = await session.get(AssistantMemoryCandidate, candidate_id)
            if candidate is None:
                raise ValueError("Fact candidate does not exist")
            candidate.promoted_memory_record_id = memory_record_id
            await session.commit()
