import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from app.modules.assistant.domain.facts import (
    ExtractedFact,
    FactClass,
    FactDecision,
    FactEvaluation,
)

STORABLE: frozenset[FactClass] = frozenset(
    {
        FactClass.PREFERENCE,
        FactClass.ENTITY_AFFINITY,
        FactClass.EPISODIC_REFERENCE,
        FactClass.DOMAIN_CONSTRAINT,
        FactClass.ATTRIBUTED_OPINION,
    }
)

TTL_DAYS: dict[FactClass, int | None] = {
    FactClass.PREFERENCE: None,
    FactClass.ENTITY_AFFINITY: 180,
    FactClass.EPISODIC_REFERENCE: 180,
    FactClass.DOMAIN_CONSTRAINT: 180,
    FactClass.ATTRIBUTED_OPINION: 90,
}

VOLATILE_VALUE_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:units?|pcs|pieces?|hours?|days?|%|usd|vnd)\b|\$\s*\d+",
    re.IGNORECASE,
)
VOLATILE_TIME_PATTERN = re.compile(
    r"\b(?:currently|right now|as of today|at the moment|today|tomorrow)\b",
    re.IGNORECASE,
)
AUTHORITATIVE_CLAIM_PATTERN = re.compile(
    r"\b(?:role|permission|authorized|authorization|site membership|works at site)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class FactAcceptancePolicy:
    max_statement_characters: int
    rederivable_terms: frozenset[str]

    def evaluate(
        self,
        fact: ExtractedFact,
        source_turn_ids: frozenset[UUID],
        now: datetime,
    ) -> FactEvaluation:
        statement = fact.statement.strip()
        if not statement:
            return FactEvaluation(FactDecision.REJECTED, "empty_statement", None)
        if len(statement) > self.max_statement_characters:
            return FactEvaluation(FactDecision.REJECTED, "statement_too_long", None)
        if not fact.evidence_turn_ids:
            return FactEvaluation(FactDecision.REJECTED, "missing_evidence", None)
        if not set(fact.evidence_turn_ids).issubset(source_turn_ids):
            return FactEvaluation(FactDecision.REJECTED, "invalid_evidence", None)
        if fact.fact_class not in STORABLE:
            return FactEvaluation(FactDecision.REJECTED, "non_storable_class", None)
        if AUTHORITATIVE_CLAIM_PATTERN.search(statement):
            return FactEvaluation(FactDecision.REJECTED, "authoritative_claim", None)
        if fact.fact_class is FactClass.ATTRIBUTED_OPINION and not statement.startswith("User "):
            return FactEvaluation(FactDecision.REJECTED, "opinion_requires_attribution", None)
        if fact.fact_class is not FactClass.DOMAIN_CONSTRAINT and (
            VOLATILE_VALUE_PATTERN.search(statement) or VOLATILE_TIME_PATTERN.search(statement)
        ):
            return FactEvaluation(FactDecision.REJECTED, "volatile_value", None)
        lowered_statement = statement.lower()
        if any(term in lowered_statement for term in self.rederivable_terms):
            return FactEvaluation(FactDecision.REJECTED, "rederivable_value", None)
        retention_days = TTL_DAYS[fact.fact_class]
        expires_at = None if retention_days is None else now + timedelta(days=retention_days)
        return FactEvaluation(FactDecision.ACCEPTED, "accepted", expires_at)
