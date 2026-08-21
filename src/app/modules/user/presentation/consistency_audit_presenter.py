from app.modules.user.application.use_cases import UserConsistencyAuditReport
from app.modules.user.contracts.consistency_auditor import (
    ConsistencySeverity,
    ConsistencyToolResultCode,
    UserConsistencyAuditorOutputV1,
    UserConsistencyFindingV1,
    UserConsistencySeverityTotalsV1,
)


def to_user_consistency_auditor_output(
    report: UserConsistencyAuditReport,
) -> UserConsistencyAuditorOutputV1:
    totals = UserConsistencySeverityTotalsV1()
    findings: list[UserConsistencyFindingV1] = []

    for item in report.findings:
        if item.severity == ConsistencySeverity.CRITICAL:
            totals.critical += 1
        elif item.severity == ConsistencySeverity.HIGH:
            totals.high += 1
        elif item.severity == ConsistencySeverity.MEDIUM:
            totals.medium += 1
        elif item.severity == ConsistencySeverity.LOW:
            totals.low += 1

        findings.append(
            UserConsistencyFindingV1(
                check_id=item.check_id,
                severity=item.severity,
                user_id=item.user_id,
                message=item.message,
                evidence=item.evidence,
            )
        )

    return UserConsistencyAuditorOutputV1(
        run_id=report.run_id,
        result_code=(
            ConsistencyToolResultCode.ISSUES_FOUND
            if report.issues_total > 0
            else ConsistencyToolResultCode.OK
        ),
        generated_at_utc=report.generated_at_utc,
        total_users=report.total_users,
        checks_executed=report.checks_executed,
        issues_total=report.issues_total,
        issues_by_severity=totals,
        findings=findings,
    )
