from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class FactClass(StrEnum):
    PREFERENCE = "preference"
    ENTITY_AFFINITY = "entity_affinity"
    EPISODIC_REFERENCE = "episodic_reference"
    DOMAIN_CONSTRAINT = "domain_constraint"
    ATTRIBUTED_OPINION = "attributed_opinion"
    METRIC_VALUE = "metric_value"
    TRANSIENT_STATE = "transient_state"


class FactDecision(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class ExtractedFact:
    statement: str
    fact_class: FactClass
    evidence_turn_ids: tuple[UUID, ...]
    entity_refs: tuple[str, ...]
    explicitly_stated: bool


@dataclass(frozen=True, slots=True)
class FactEvaluation:
    decision: FactDecision
    reason: str
    expires_at_utc: datetime | None
