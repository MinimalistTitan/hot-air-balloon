from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.assistant.application.reference_resolution.contracts import (
    FieldQueryStatus,
    ReferenceOperation,
    ResolutionStatus,
)
from app.modules.assistant.application.reference_resolution.field_query import FieldQueryExecutor
from app.modules.assistant.application.reference_resolution.formatting import (
    FieldValueFormatterRegistry,
)
from app.modules.assistant.application.reference_resolution.parser import (
    RegexReferenceQueryParser,
)
from app.modules.assistant.application.reference_resolution.policy import (
    ReferenceFieldPolicy,
    ReferenceResolutionPolicy,
)
from app.modules.assistant.application.reference_resolution.resolver import (
    MappingValueRanker,
    ReferenceResolver,
)
from app.modules.assistant.domain.conversation_evidence import ConversationEvidenceSnapshot
from app.shared.kernel.response_evidence import CollectionEvidence, EvidenceField, EvidenceItem

CONVERSATION_ID = UUID("11111111-1111-1111-1111-111111111111")
OWNER_ID = UUID("22222222-2222-2222-2222-222222222222")

PARSER = RegexReferenceQueryParser(
    field_patterns=((r"\bdue\b", "due_at"), (r"\bpriority\b", "priority")),
    maximum_patterns=(r"\bhighest\b",),
)
RESOLVER = ReferenceResolver(
    parser=PARSER,
    rankers={"priority": MappingValueRanker({"low": 1, "medium": 2, "high": 3})},
)


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
                filters=(),
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
                    EvidenceItem(
                        evidence_id="work-orders:WO-HCM-0001",
                        entity_id="WO-HCM-0001",
                        label="WO-HCM-0001 - Replace CNC spindle bearing",
                        fields=(
                            EvidenceField("priority", "Priority", "high"),
                            EvidenceField("due_at", "Due", "2026-08-15T08:00:00+00:00"),
                        ),
                    ),
                ),
            ),
        ),
        created_at_utc=datetime(2026, 9, 3, tzinfo=UTC),
        expires_at_utc=None,
    )


def test_resolves_plural_due_date_after_intermediate_question() -> None:
    outcome = RESOLVER.resolve("When are they due?", [_snapshot()])

    assert outcome.status is ResolutionStatus.RESOLVED
    assert outcome.reference is not None
    assert outcome.reference.request.operation is ReferenceOperation.FIELD
    assert outcome.reference.request.field_name == "due_at"
    assert [item.entity_id for item in outcome.reference.items] == ["WO-HCM-0101", "WO-HCM-0001"]


def test_resolves_highest_priority_and_returns_all_ties() -> None:
    outcome = RESOLVER.resolve(
        "Which ones have the highest priority from the previous work orders?",
        [_snapshot()],
    )

    assert outcome.status is ResolutionStatus.RESOLVED
    assert outcome.reference is not None
    assert outcome.reference.request.operation is ReferenceOperation.MAXIMUM
    assert [item.entity_id for item in outcome.reference.items] == ["WO-HCM-0101", "WO-HCM-0001"]


def test_resolves_ordinal_due_date() -> None:
    outcome = RESOLVER.resolve("When is the second one due?", [_snapshot()])

    assert outcome.reference is not None
    assert [item.entity_id for item in outcome.reference.items] == ["WO-HCM-0001"]


def test_field_query_reports_partial_values_without_dropping_entities() -> None:
    outcome = RESOLVER.resolve("When are they due?", [_snapshot()])
    assert outcome.reference is not None
    reference = outcome.reference
    partial_reference = type(reference)(
        entity_label=reference.entity_label,
        items=(
            reference.items[0],
            type(reference.items[1])(
                evidence_id=reference.items[1].evidence_id,
                entity_id=reference.items[1].entity_id,
                label=reference.items[1].label,
                fields=(),
            ),
        ),
        request=reference.request,
    )

    result = FieldQueryExecutor().execute(partial_reference)

    assert result.status is FieldQueryStatus.PARTIAL
    assert [(value.entity_id, value.value) for value in result.values] == [
        ("WO-HCM-0101", "2026-08-28T08:00:00+00:00"),
        ("WO-HCM-0001", None),
    ]


def test_resolver_is_neutral_about_entity_and_field_names() -> None:
    snapshot = _snapshot()
    generic_snapshot = ConversationEvidenceSnapshot(
        conversation_id=snapshot.conversation_id,
        owner_user_id=snapshot.owner_user_id,
        exchange_id=uuid4(),
        tool_name="list_assets",
        evidence=(
            CollectionEvidence(
                evidence_id="assets",
                entity_label="asset",
                entity_label_plural="assets",
                filters=(),
                requested_count=None,
                items=(
                    EvidenceItem(
                        evidence_id="assets:A-1",
                        entity_id="A-1",
                        label="A-1",
                        fields=(EvidenceField("owner", "Owner", "Operations"),),
                    ),
                ),
            ),
        ),
        created_at_utc=snapshot.created_at_utc,
        expires_at_utc=None,
    )
    parser = RegexReferenceQueryParser(field_patterns=((r"\bowner\b", "owner"),))
    outcome = ReferenceResolver(parser, {}).resolve(
        "What is the owner of the previous item?",
        [generic_snapshot],
    )

    assert outcome.reference is not None
    result = FieldQueryExecutor().execute(outcome.reference)
    assert result.status is FieldQueryStatus.COMPLETE
    assert result.entity_label == "asset"
    assert FieldValueFormatterRegistry({}).format(result) == "A-1: Operations"


def test_policy_registers_new_fields_without_wiring_changes() -> None:
    policy = ReferenceResolutionPolicy(
        fields=(
            ReferenceFieldPolicy(
                field_name="owner",
                query_patterns=(r"\bowner\b",),
            ),
        )
    )
    snapshot = _snapshot()
    generic_snapshot = ConversationEvidenceSnapshot(
        conversation_id=snapshot.conversation_id,
        owner_user_id=snapshot.owner_user_id,
        exchange_id=uuid4(),
        tool_name="list_assets",
        evidence=(
            CollectionEvidence(
                evidence_id="assets",
                entity_label="asset",
                entity_label_plural="assets",
                filters=(),
                requested_count=None,
                items=(
                    EvidenceItem(
                        evidence_id="assets:A-1",
                        entity_id="A-1",
                        label="A-1",
                        fields=(EvidenceField("owner", "Owner", "Operations"),),
                    ),
                ),
            ),
        ),
        created_at_utc=snapshot.created_at_utc,
        expires_at_utc=None,
    )

    outcome = policy.build_resolver().resolve(
        "What is the owner of the previous item?",
        [generic_snapshot],
    )

    assert outcome.reference is not None
    result = FieldQueryExecutor().execute(outcome.reference)
    assert policy.build_formatter_registry().format(result) == "A-1: Operations"


@pytest.mark.parametrize(
    "query",
    ["Show me open work orders", "When are work orders due?", "What is the priority?"],
)
def test_does_not_resolve_unscoped_or_non_reference_queries(query: str) -> None:
    assert RESOLVER.resolve(query, [_snapshot()]).status is ResolutionStatus.NO_REFERENCE
