from dataclasses import dataclass
from enum import StrEnum

from app.shared.kernel.response_evidence import EvidenceItem


class ReferenceOperation(StrEnum):
    FIELD = "field"
    MAXIMUM = "maximum"
    MINIMUM = "minimum"


class ResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    NO_REFERENCE = "no_reference"
    NO_EVIDENCE = "no_evidence"
    AMBIGUOUS = "ambiguous"


class FieldQueryStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    EMPTY = "empty"


@dataclass(frozen=True, slots=True)
class ReferenceRequest:
    field_name: str
    operation: ReferenceOperation = ReferenceOperation.FIELD
    ordinal: int | None = None


@dataclass(frozen=True, slots=True)
class ResolvedReference:
    entity_label: str
    items: tuple[EvidenceItem, ...]
    request: ReferenceRequest


@dataclass(frozen=True, slots=True)
class ResolutionOutcome:
    status: ResolutionStatus
    reference: ResolvedReference | None = None


@dataclass(frozen=True, slots=True)
class FieldValue:
    entity_id: str
    label: str
    field_name: str
    value: str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class FieldQueryResult:
    entity_label: str
    field_name: str
    values: tuple[FieldValue, ...]
    status: FieldQueryStatus