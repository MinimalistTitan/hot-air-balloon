from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.modules.assistant.application.reference_resolution.contracts import (
    ReferenceOperation,
    ReferenceRequest,
    ResolutionOutcome,
    ResolutionStatus,
    ResolvedReference,
)
from app.modules.assistant.application.reference_resolution.parser import ReferenceQueryParser
from app.modules.assistant.domain.conversation_evidence import ConversationEvidenceSnapshot
from app.shared.kernel.response_evidence import CollectionEvidence, EvidenceItem


class ReferenceValueRanker(Protocol):
    def rank(self, value: object) -> int | None: ...


@dataclass(frozen=True, slots=True)
class MappingValueRanker:
    values: Mapping[str, int]

    def rank(self, value: object) -> int | None:
        return self.values.get(value.casefold()) if isinstance(value, str) else None


@dataclass(frozen=True, slots=True)
class ReferenceResolver:
    parser: ReferenceQueryParser
    rankers: Mapping[str, ReferenceValueRanker]

    def resolve(
        self,
        query: str,
        snapshots: Sequence[ConversationEvidenceSnapshot],
    ) -> ResolutionOutcome:
        request = self.parser.parse(query)
        if request is None:
            return ResolutionOutcome(ResolutionStatus.NO_REFERENCE)
        collection = _latest_collection(snapshots)
        if collection is None:
            return ResolutionOutcome(ResolutionStatus.NO_EVIDENCE)
        items = _select_items(collection.items, request.ordinal)
        if not items:
            return ResolutionOutcome(ResolutionStatus.AMBIGUOUS)
        if request.operation is not ReferenceOperation.FIELD:
            ranker = self.rankers.get(request.field_name)
            if ranker is None:
                return ResolutionOutcome(ResolutionStatus.AMBIGUOUS)
            items = _ranked_items(items, request, ranker)
            if not items:
                return ResolutionOutcome(ResolutionStatus.AMBIGUOUS)
        return ResolutionOutcome(
            ResolutionStatus.RESOLVED,
            ResolvedReference(collection.entity_label, items, request),
        )


def _latest_collection(
    snapshots: Sequence[ConversationEvidenceSnapshot],
) -> CollectionEvidence | None:
    for snapshot in reversed(snapshots):
        for evidence in reversed(snapshot.evidence):
            if isinstance(evidence, CollectionEvidence) and evidence.items:
                return evidence
    return None


def _select_items(items: tuple[EvidenceItem, ...], ordinal: int | None) -> tuple[EvidenceItem, ...]:
    if ordinal is None:
        return items
    return (items[ordinal],) if 0 <= ordinal < len(items) else ()


def _ranked_items(
    items: tuple[EvidenceItem, ...],
    request: ReferenceRequest,
    ranker: ReferenceValueRanker,
) -> tuple[EvidenceItem, ...]:
    ranked: list[tuple[EvidenceItem, int]] = []
    for item in items:
        value = ranker.rank(_field_value(item, request.field_name))
        if value is not None:
            ranked.append((item, value))
    if not ranked:
        return ()
    target = (
        max(value for _, value in ranked)
        if request.operation is ReferenceOperation.MAXIMUM
        else min(value for _, value in ranked)
    )
    return tuple(item for item, value in ranked if value == target)


def _field_value(item: EvidenceItem, field_name: str) -> object:
    return next((field.value for field in item.fields if field.name == field_name), None)
