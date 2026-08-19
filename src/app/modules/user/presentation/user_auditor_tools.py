from typing import Any

from app.modules.assistant.tool_gateway.domain import ToolDefinition, ToolRateLimit
from app.modules.user.application.ports import UserUnitOfWorkFactory
from app.modules.user.application.use_cases import (
    RunUserConsistencyAudit,
    UserConsistencyAuditCommand,
    UserConsistencyAuditReport,
)
from app.modules.user.contracts.consistency_auditor import (
    TOOL_USERS_CONSISTENCY_AUDITOR_V1,
    ConsistencySeverity,
    ConsistencyToolResultCode,
    UserConsistencyAuditorInputV1,
    UserConsistencyAuditorOutputV1,
    UserConsistencyFindingV1,
    UserConsistencySeverityTotalsV1,
)
from app.modules.user.domain.authorization import Permission


def build_users_consistency_auditor_tool(
    unit_of_work_factory: UserUnitOfWorkFactory,
) -> ToolDefinition:
    use_case = RunUserConsistencyAudit(unit_of_work_factory=unit_of_work_factory)

    async def invoke(payload: dict[str, Any]) -> dict[str, Any]:
        data = UserConsistencyAuditorInputV1.model_validate(payload)

        command = UserConsistencyAuditCommand(
            checks=tuple(check.value for check in data.checks) if data.checks else None,
            limit_per_check=data.limit_per_check,
            run_id=data.run_id,
            now_utc=data.now_utc,
        )
        report = await use_case.execute(command)

        output = to_user_consistency_auditor_output(report)
        return output.model_dump(mode="json")

    return ToolDefinition(
        name=TOOL_USERS_CONSISTENCY_AUDITOR_V1,
        description="Deterministic consistency audit for users table",
        input_model=UserConsistencyAuditorInputV1,
        output_model=UserConsistencyAuditorOutputV1,
        handler=invoke,
        required_permission=Permission.AUDIT_LOGS_READ,
        rate_limit=ToolRateLimit(max_calls=5, window_seconds=60),
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