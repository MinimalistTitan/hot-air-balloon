from typing import Any

from app.modules.assistant.tool_gateway.domain import ToolDefinition, ToolRateLimit
from app.modules.user.application.ports import UserUnitOfWorkFactory
from app.modules.user.application.use_cases import (
    RunUserConsistencyAudit,
    UserConsistencyAuditCommand,
)
from app.modules.user.contracts.consistency_auditor import (
    TOOL_USERS_CONSISTENCY_AUDITOR_V1,
    UserConsistencyAuditorInputV1,
    UserConsistencyAuditorOutputV1,
)
from app.modules.user.domain.authorization import Permission
from app.modules.user.presentation.consistency_audit_presenter import (
    to_user_consistency_auditor_output,
)


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
        description=(
            "Run a read-only deterministic consistency audit of the internal users table for "
            "duplicate emails, invalid timestamps, names, and status mismatches. Use only when "
            "the user explicitly requests a user-data consistency audit. Do not use for ordinary "
            "user lookup, ERP operations, maintenance questions, or general explanations."
        ),
        input_model=UserConsistencyAuditorInputV1,
        output_model=UserConsistencyAuditorOutputV1,
        handler=invoke,
        required_permission=Permission.AUDIT_LOGS_READ,
        rate_limit=ToolRateLimit(max_calls=5, window_seconds=60),
    )
