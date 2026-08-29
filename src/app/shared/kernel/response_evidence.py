from dataclasses import dataclass, field
from typing import Literal

type EvidenceScalar = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class EvidenceField:
    name: str
    label: str
    value: EvidenceScalar


@dataclass(frozen=True, slots=True)
class SourceReference:
    source_id: str
    title: str
    url: str
    published_at: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    evidence_id: str
    entity_id: str
    label: str
    fields: tuple[EvidenceField, ...] = ()
    source: SourceReference | None = None


@dataclass(frozen=True, slots=True)
class CollectionEvidence:
    evidence_id: str
    entity_label: str
    entity_label_plural: str
    filters: tuple[EvidenceField, ...]
    requested_count: int | None
    items: tuple[EvidenceItem, ...]
    type: Literal["collection"] = field(default="collection", init=False)


@dataclass(frozen=True, slots=True)
class MutationEvidence:
    evidence_id: str
    entity_label: str
    entity_id: str
    previous_state: str | None
    current_state: str
    changed: bool
    type: Literal["mutation"] = field(default="mutation", init=False)


@dataclass(frozen=True, slots=True)
class ActionRequiredEvidence:
    evidence_id: str
    action: str
    reason: str
    type: Literal["action_required"] = field(default="action_required", init=False)


@dataclass(frozen=True, slots=True)
class FailureEvidence:
    evidence_id: str
    code: str
    message: str
    retryable: bool
    type: Literal["failure"] = field(default="failure", init=False)


type EvidenceBlock = (
    CollectionEvidence | MutationEvidence | ActionRequiredEvidence | FailureEvidence
)


class EvidenceAdaptationError(ValueError):
    pass
