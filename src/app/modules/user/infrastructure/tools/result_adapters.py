from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel

from app.modules.user.contracts.consistency_auditor import (
    TOOL_USERS_CONSISTENCY_AUDITOR_V1,
    ConsistencyToolResultCode,
    UserConsistencyAuditorOutputV1,
)
from app.shared.kernel.response_evidence import (
    CollectionEvidence,
    EvidenceAdaptationError,
    EvidenceBlock,
    EvidenceField,
    EvidenceItem,
    FailureEvidence,
)


@dataclass(frozen=True, slots=True)
class UserConsistencyAuditResultAdapter:
    def to_evidence(
        self,
        *,
        applied_payload: Mapping[str, object],
        output: BaseModel,
    ) -> tuple[EvidenceBlock, ...]:
        if not isinstance(output, UserConsistencyAuditorOutputV1):
            raise EvidenceAdaptationError("unexpected user consistency audit output type")

        if output.tool_name != TOOL_USERS_CONSISTENCY_AUDITOR_V1:
            raise EvidenceAdaptationError("user consistency audit tool identity does not match")

        severity_totals = output.issues_by_severity
        severity_count = (
            severity_totals.critical
            + severity_totals.high
            + severity_totals.medium
            + severity_totals.low
        )

        if output.total_users < 0 or output.checks_executed < 0:
            raise EvidenceAdaptationError("user consistency audit contains negative totals")

        if output.issues_total != len(output.findings):
            raise EvidenceAdaptationError("issues_total does not match the number of findings")

        if severity_count != output.issues_total:
            raise EvidenceAdaptationError("severity totals do not match issues_total")

        if output.result_code is ConsistencyToolResultCode.FAILED:
            return (
                FailureEvidence(
                    evidence_id=(f"user-consistency-audit:{output.run_id}:failure"),
                    code="user_consistency_audit_failed",
                    message="The user consistency audit failed.",
                    retryable=False,
                ),
            )

        if output.result_code is ConsistencyToolResultCode.OK and output.issues_total != 0:
            raise EvidenceAdaptationError("an OK audit result cannot contain findings")

        if (
            output.result_code is ConsistencyToolResultCode.ISSUES_FOUND
            and output.issues_total == 0
        ):
            raise EvidenceAdaptationError("an issues-found result must contain findings")

        filters = self._filters(applied_payload)
        run_evidence_id = f"user-consistency-audit:{output.run_id}"

        items = tuple(
            EvidenceItem(
                evidence_id=f"{run_evidence_id}:finding:{index}",
                entity_id=(
                    str(finding.user_id)
                    if finding.user_id is not None
                    else f"{finding.check_id}:{index}"
                ),
                label=finding.message,
                fields=(
                    EvidenceField(
                        name="check_id",
                        label="Check",
                        value=finding.check_id,
                    ),
                    EvidenceField(
                        name="severity",
                        label="Severity",
                        value=finding.severity.value,
                    ),
                    *(
                        (
                            EvidenceField(
                                name="user_id",
                                label="User ID",
                                value=str(finding.user_id),
                            ),
                        )
                        if finding.user_id is not None
                        else ()
                    ),
                ),
            )
            for index, finding in enumerate(output.findings, start=1)
        )

        return (
            CollectionEvidence(
                evidence_id=run_evidence_id,
                entity_label="user consistency issue",
                entity_label_plural="user consistency issues",
                filters=filters,
                requested_count=None,
                items=items,
            ),
        )

    def _filters(
        self,
        applied_payload: Mapping[str, object],
    ) -> tuple[EvidenceField, ...]:
        selected_checks = applied_payload.get("checks")
        if selected_checks is None:
            return ()

        if not isinstance(selected_checks, list) or any(
            not isinstance(check, str) for check in selected_checks
        ):
            raise EvidenceAdaptationError("applied audit checks are malformed")

        if not selected_checks:
            return ()

        return (
            EvidenceField(
                name="checks",
                label="Checks",
                value=", ".join(selected_checks),
            ),
        )


USER_CONSISTENCY_AUDIT_RESULT_ADAPTER = UserConsistencyAuditResultAdapter()
