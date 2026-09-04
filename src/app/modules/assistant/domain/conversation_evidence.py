from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.shared.kernel.response_evidence import (
    ActionRequiredEvidence,
    CollectionEvidence,
    EvidenceBlock,
    EvidenceField,
    EvidenceItem,
    FailureEvidence,
    MutationEvidence,
)

EVIDENCE_SCHEMA_VERSION = 1
MAX_SERIALIZED_EVIDENCE_BYTES = 128_000


@dataclass(frozen=True, slots=True)
class ConversationEvidenceSnapshot:
    conversation_id: UUID
    owner_user_id: UUID
    exchange_id: UUID
    tool_name: str
    evidence: tuple[EvidenceBlock, ...]
    created_at_utc: datetime
    expires_at_utc: datetime | None
    schema_version: int = EVIDENCE_SCHEMA_VERSION

    def to_context_text(self) -> str:
        sections: list[str] = []
        for block in self.evidence:
            if isinstance(block, CollectionEvidence):
                items = []
                for item in block.items:
                    fields = ", ".join(
                        f"{field.name}={field.value}" for field in item.fields
                    )
                    items.append(f"entity_id={item.entity_id}; label={item.label}; {fields}")
                sections.append(
                    f"type=collection; entity={block.entity_label_plural}; "
                    + " | ".join(items)
                )
            else:
                sections.append(json.dumps(_serialize_block(block), sort_keys=True))
        return (
            f"conversation_id={self.conversation_id}; exchange_id={self.exchange_id}; "
            + "\n".join(sections)
        )

    def to_json(self) -> dict[str, object]:
        if self.schema_version != EVIDENCE_SCHEMA_VERSION:
            raise ValueError("unsupported evidence schema version")
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "exchange_id": str(self.exchange_id),
            "tool_name": self.tool_name,
            "evidence": [_serialize_block(block) for block in self.evidence],
        }
        serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
        if len(serialized.encode("utf-8")) > MAX_SERIALIZED_EVIDENCE_BYTES:
            raise ValueError("evidence payload exceeds size limit")
        return payload

    @classmethod
    def from_json(
        cls,
        *,
        conversation_id: UUID,
        owner_user_id: UUID,
        created_at_utc: datetime,
        expires_at_utc: datetime | None,
        payload: Mapping[str, object],
    ) -> ConversationEvidenceSnapshot:
        if payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
            raise ValueError("unsupported evidence schema version")
        raw_evidence = payload.get("evidence")
        if not isinstance(raw_evidence, list):
            raise ValueError("evidence payload must contain a list")
        snapshot = cls(
            conversation_id=conversation_id,
            owner_user_id=owner_user_id,
            exchange_id=UUID(_required_string(payload, "exchange_id")),
            tool_name=_required_string(payload, "tool_name"),
            evidence=tuple(_deserialize_block(item) for item in raw_evidence),
            created_at_utc=created_at_utc,
            expires_at_utc=expires_at_utc,
        )
        snapshot.to_json()
        return snapshot


def _serialize_field(field: EvidenceField) -> dict[str, object]:
    return {"name": field.name, "label": field.label, "value": field.value}


def _deserialize_field(value: object) -> EvidenceField:
    data = _mapping(value)
    field_value = data.get("value")
    if field_value is not None and not isinstance(field_value, (str, int, float, bool)):
        raise ValueError("evidence field value has an unsupported type")
    return EvidenceField(
        name=_required_string(data, "name"),
        label=_required_string(data, "label"),
        value=field_value,
    )


def _serialize_item(item: EvidenceItem) -> dict[str, object]:
    return {
        "evidence_id": item.evidence_id,
        "entity_id": item.entity_id,
        "label": item.label,
        "fields": [_serialize_field(field) for field in item.fields],
    }


def _deserialize_item(value: object) -> EvidenceItem:
    data = _mapping(value)
    raw_fields = data.get("fields", [])
    if not isinstance(raw_fields, list):
        raise ValueError("evidence item fields must be a list")
    return EvidenceItem(
        evidence_id=_required_string(data, "evidence_id"),
        entity_id=_required_string(data, "entity_id"),
        label=_required_string(data, "label"),
        fields=tuple(_deserialize_field(item) for item in raw_fields),
    )


def _serialize_block(block: EvidenceBlock) -> dict[str, object]:
    match block:
        case CollectionEvidence():
            return {
                "type": "collection",
                "evidence_id": block.evidence_id,
                "entity_label": block.entity_label,
                "entity_label_plural": block.entity_label_plural,
                "filters": [_serialize_field(field) for field in block.filters],
                "requested_count": block.requested_count,
                "items": [_serialize_item(item) for item in block.items],
            }
        case MutationEvidence():
            return {
                "type": "mutation",
                "evidence_id": block.evidence_id,
                "entity_label": block.entity_label,
                "entity_id": block.entity_id,
                "previous_state": block.previous_state,
                "current_state": block.current_state,
                "changed": block.changed,
            }
        case ActionRequiredEvidence():
            return {
                "type": "action_required",
                "evidence_id": block.evidence_id,
                "action": block.action,
                "reason": block.reason,
            }
        case FailureEvidence():
            return {
                "type": "failure",
                "evidence_id": block.evidence_id,
                "code": block.code,
                "message": block.message,
                "retryable": block.retryable,
            }


def _deserialize_block(value: object) -> EvidenceBlock:
    data = _mapping(value)
    block_type = _required_string(data, "type")
    if block_type == "collection":
        raw_filters = data.get("filters", [])
        raw_items = data.get("items", [])
        if not isinstance(raw_filters, list) or not isinstance(raw_items, list):
            raise ValueError("collection evidence fields must be lists")
        requested_count = data.get("requested_count")
        if requested_count is not None and (
            not isinstance(requested_count, int) or isinstance(requested_count, bool)
        ):
            raise ValueError("requested count must be an integer")
        return CollectionEvidence(
            evidence_id=_required_string(data, "evidence_id"),
            entity_label=_required_string(data, "entity_label"),
            entity_label_plural=_required_string(data, "entity_label_plural"),
            filters=tuple(_deserialize_field(item) for item in raw_filters),
            requested_count=requested_count,
            items=tuple(_deserialize_item(item) for item in raw_items),
        )
    if block_type == "mutation":
        return MutationEvidence(
            evidence_id=_required_string(data, "evidence_id"),
            entity_label=_required_string(data, "entity_label"),
            entity_id=_required_string(data, "entity_id"),
            previous_state=_optional_string(data, "previous_state"),
            current_state=_required_string(data, "current_state"),
            changed=_required_bool(data, "changed"),
        )
    if block_type == "action_required":
        return ActionRequiredEvidence(
            evidence_id=_required_string(data, "evidence_id"),
            action=_required_string(data, "action"),
            reason=_required_string(data, "reason"),
        )
    if block_type == "failure":
        return FailureEvidence(
            evidence_id=_required_string(data, "evidence_id"),
            code=_required_string(data, "code"),
            message=_required_string(data, "message"),
            retryable=_required_bool(data, "retryable"),
        )
    raise ValueError("unsupported evidence block type")


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("evidence value must be an object")
    return value


def _required_string(data: Mapping[str, object], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"evidence field {name} must be a non-empty string")
    return value


def _optional_string(data: Mapping[str, object], name: str) -> str | None:
    value = data.get(name)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"evidence field {name} must be a string or null")
    return value


def _required_bool(data: Mapping[str, object], name: str) -> bool:
    value = data.get(name)
    if not isinstance(value, bool):
        raise ValueError(f"evidence field {name} must be a boolean")
    return value
