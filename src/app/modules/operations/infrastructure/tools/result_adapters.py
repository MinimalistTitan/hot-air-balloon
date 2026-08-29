from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel

from app.shared.kernel.response_evidence import (
    CollectionEvidence,
    EvidenceAdaptationError,
    EvidenceField,
    EvidenceItem,
    FailureEvidence,
    MutationEvidence,
)


@dataclass(frozen=True, slots=True)
class WorkOrderMutationAdapter:
    def to_evidence(
        self,
        *,
        applied_payload: Mapping[str, object],
        output: BaseModel,
    ) -> tuple[MutationEvidence | FailureEvidence, ...]:
        data = output.model_dump(mode="json")

        if data.get("succeeded") is not True:
            return (
                FailureEvidence(
                    evidence_id="work-order-status:failure",
                    code=str(data.get("error_code") or "mutation_rejected"),
                    message=str(data.get("error_message") or "The status change was rejected."),
                    retryable=False,
                ),
            )

        entity_id = data.get("work_order_code") or data.get("work_order_id")
        current_state = data.get("current_status")
        if entity_id is None or not isinstance(current_state, str):
            raise EvidenceAdaptationError("successful mutation lacks identity or resulting state")

        return (
            MutationEvidence(
                evidence_id="work-order-status",
                entity_label="work order",
                entity_id=str(entity_id),
                previous_state=(
                    str(data["previous_status"])
                    if data.get("previous_status") is not None
                    else None
                ),
                current_state=current_state,
                changed=data.get("changed") is True,
            ),
        )


@dataclass(frozen=True, slots=True)
class CollectionResultAdapter:
    evidence_id: str
    collection_field: str
    entity_label: str
    entity_label_plural: str
    identifier_fields: tuple[str, ...]
    label_fields: tuple[str, ...]
    displayed_fields: tuple[tuple[str, str], ...]
    filter_fields: tuple[tuple[str, str], ...]
    order_field: str | None = None

    def to_evidence(
        self,
        *,
        applied_payload: Mapping[str, object],
        output: BaseModel,
    ) -> tuple[CollectionEvidence, ...]:
        data = output.model_dump(mode="json")
        records = data.get(self.collection_field)
        if not isinstance(records, list):
            raise EvidenceAdaptationError("collection is missing")

        limit = applied_payload.get("limit")
        requested_count = limit if isinstance(limit, int) and not isinstance(limit, bool) else None
        if requested_count is not None and len(records) > requested_count:
            raise EvidenceAdaptationError("collection exceeds applied limit")

        filters = tuple(
            EvidenceField(name=name, label=label, value=value)  # type: ignore
            for name, label in self.filter_fields
            if (value := applied_payload.get(name)) is not None
        )

        items: list[EvidenceItem] = []
        ordered_values: list[str] = []

        for record in records:
            if not isinstance(record, dict):
                raise EvidenceAdaptationError("record is not an object")

            for filter_name, _ in self.filter_fields:
                expected = applied_payload.get(filter_name)
                actual = record.get(filter_name)
                if expected is not None and str(actual).casefold() != str(expected).casefold():
                    raise EvidenceAdaptationError(f"record conflicts with {filter_name}")

            entity_id = next(
                (
                    str(record[field])
                    for field in self.identifier_fields
                    if record.get(field) is not None
                ),
                None,
            )
            if entity_id is None:
                raise EvidenceAdaptationError("record has no identifier")

            label_parts = [
                str(record[field]) for field in self.label_fields if record.get(field) is not None
            ]
            label = " - ".join(label_parts) or entity_id

            items.append(
                EvidenceItem(
                    evidence_id=f"{self.evidence_id}:{entity_id}",
                    entity_id=entity_id,
                    label=label,
                    fields=tuple(
                        EvidenceField(
                            name=name,
                            label=field_label,
                            value=record[name],
                        )
                        for name, field_label in self.displayed_fields
                        if record.get(name) is not None
                    ),
                )
            )

            if self.order_field is not None:
                value = record.get(self.order_field)
                if not isinstance(value, str):
                    raise EvidenceAdaptationError(f"record lacks {self.order_field}")
                ordered_values.append(value)

        if ordered_values != sorted(ordered_values):
            raise EvidenceAdaptationError("records are incorrectly ordered")

        return (
            CollectionEvidence(
                evidence_id=self.evidence_id,
                entity_label=self.entity_label,
                entity_label_plural=self.entity_label_plural,
                filters=filters,
                requested_count=requested_count,
                items=tuple(items),
            ),
        )


WORK_ORDERS_ADAPTER = CollectionResultAdapter(
    evidence_id="work-orders",
    collection_field="work_orders",
    entity_label="work order",
    entity_label_plural="work orders",
    identifier_fields=("code", "id"),
    label_fields=("code", "title"),
    displayed_fields=(
        ("status", "Status"),
        ("priority", "Priority"),
        ("due_at", "Due"),
    ),
    filter_fields=(("site_code", "Site"), ("status", "Status")),
)

ASSETS_ADAPTER = CollectionResultAdapter(
    evidence_id="assets",
    collection_field="assets",
    entity_label="asset",
    entity_label_plural="assets",
    identifier_fields=("code", "id"),
    label_fields=("code", "name"),
    displayed_fields=(
        ("status", "Status"),
        ("criticality", "Criticality"),
    ),
    filter_fields=(("site_code", "Site"),),
)

MAINTENANCE_TICKETS_ADAPTER = CollectionResultAdapter(
    evidence_id="maintenance-tickets",
    collection_field="tickets",
    entity_label="maintenance ticket",
    entity_label_plural="maintenance tickets",
    identifier_fields=("code", "ticket_id"),
    label_fields=("code", "title"),
    displayed_fields=(
        ("status", "Status"),
        ("priority", "Priority"),
        ("due_at", "Due"),
    ),
    filter_fields=(("site_code", "Site"),),
)

SPARE_PARTS_ADAPTER = CollectionResultAdapter(
    evidence_id="spare-parts",
    collection_field="spare_parts",
    entity_label="spare part",
    entity_label_plural="spare parts",
    identifier_fields=("code", "part_id"),
    label_fields=("code", "name"),
    displayed_fields=(
        ("on_hand_qty", "On hand"),
        ("reorder_point", "Reorder point"),
        ("below_reorder", "Below reorder"),
    ),
    filter_fields=(("site_code", "Site"),),
)

PRODUCTION_SCHEDULE_ADAPTER = CollectionResultAdapter(
    evidence_id="production-schedule",
    collection_field="schedule",
    entity_label="scheduled work order",
    entity_label_plural="scheduled work orders",
    identifier_fields=("code", "id"),
    label_fields=("code", "title"),
    displayed_fields=(
        ("status", "Status"),
        ("due_at", "Due"),
        ("priority", "Priority"),
    ),
    filter_fields=(("site_code", "Site"),),
    order_field="due_at",
)
