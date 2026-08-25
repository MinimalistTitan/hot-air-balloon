from datetime import UTC, datetime
from uuid import uuid4

from app.modules.assistant.application.facts.act_policy import FactAcceptancePolicy
from app.modules.assistant.domain.facts import ExtractedFact, FactClass, FactDecision


def test_policy_accepts_grounded_preference() -> None:
    turn_id = uuid4()
    result = FactAcceptancePolicy(
        max_statement_characters=500,
        rederivable_terms=frozenset({"quantity on hand"}),
    ).evaluate(
        ExtractedFact(
            statement="User prefers concise daily maintenance summaries.",
            fact_class=FactClass.PREFERENCE,
            evidence_turn_ids=(turn_id,),
            entity_refs=(),
            explicitly_stated=True,
        ),
        frozenset({turn_id}),
        datetime.now(UTC),
    )

    assert result.decision is FactDecision.ACCEPTED
    assert result.expires_at_utc is None


def test_policy_rejects_ungrounded_or_volatile_facts() -> None:
    turn_id = uuid4()
    policy = FactAcceptancePolicy(max_statement_characters=500, rederivable_terms=frozenset())

    missing_evidence = policy.evaluate(
        ExtractedFact(
            statement="User prefers concise updates.",
            fact_class=FactClass.PREFERENCE,
            evidence_turn_ids=(),
            entity_refs=(),
            explicitly_stated=True,
        ),
        frozenset({turn_id}),
        datetime.now(UTC),
    )
    volatile = policy.evaluate(
        ExtractedFact(
            statement="SK-220 has 0 units currently.",
            fact_class=FactClass.METRIC_VALUE,
            evidence_turn_ids=(turn_id,),
            entity_refs=("SK-220",),
            explicitly_stated=False,
        ),
        frozenset({turn_id}),
        datetime.now(UTC),
    )

    assert missing_evidence.decision is FactDecision.REJECTED
    assert missing_evidence.reason == "missing_evidence"
    assert volatile.decision is FactDecision.REJECTED
    assert volatile.reason == "non_storable_class"
