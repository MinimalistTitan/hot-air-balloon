from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.assistant.domain.conversation_evidence import ConversationEvidenceSnapshot
from app.shared.kernel.response_evidence import (
    CollectionEvidence,
    EvidenceField,
    EvidenceItem,
)

CONVERSATION_ID = UUID("11111111-1111-1111-1111-111111111111")
OWNER_ID = UUID("22222222-2222-2222-2222-222222222222")
CREATED_AT = datetime(2026, 9, 3, 7, 0, tzinfo=UTC)


def _snapshot() -> ConversationEvidenceSnapshot:
    return ConversationEvidenceSnapshot(
        conversation_id=CONVERSATION_ID,
        owner_user_id=OWNER_ID,
        exchange_id=uuid4(),
        tool_name="get_work_orders",
        evidence=(
            CollectionEvidence(
                evidence_id="work-orders",
                entity_label="work order",
                entity_label_plural="work orders",
                filters=(EvidenceField("site_code", "Site", "PLANT-HCM"),),
                requested_count=3,
                items=(
                    EvidenceItem(
                        evidence_id="work-orders:WO-HCM-0101",
                        entity_id="WO-HCM-0101",
                        label="WO-HCM-0101 - Inspect stamping press hydraulic circuit",
                        fields=(
                            EvidenceField("priority", "Priority", "high"),
                            EvidenceField("due_at", "Due", "2026-08-28T08:00:00+00:00"),
                        ),
                    ),
                ),
            ),
        ),
        created_at_utc=CREATED_AT,
        expires_at_utc=None,
    )


def test_evidence_snapshot_round_trips_typed_blocks() -> None:
    snapshot = _snapshot()
    restored = ConversationEvidenceSnapshot.from_json(
        conversation_id=snapshot.conversation_id,
        owner_user_id=snapshot.owner_user_id,
        created_at_utc=snapshot.created_at_utc,
        expires_at_utc=snapshot.expires_at_utc,
        payload=snapshot.to_json(),
    )

    assert restored == snapshot


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": 99, "evidence": []},
        {"schema_version": 1, "evidence": "invalid"},
        {
            "schema_version": 1,
            "exchange_id": str(uuid4()),
            "tool_name": "get_work_orders",
            "evidence": [{"type": "unknown"}],
        },
    ],
)
def test_evidence_snapshot_rejects_invalid_payload(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ConversationEvidenceSnapshot.from_json(
            conversation_id=CONVERSATION_ID,
            owner_user_id=OWNER_ID,
            created_at_utc=CREATED_AT,
            expires_at_utc=None,
            payload=payload,
        )
