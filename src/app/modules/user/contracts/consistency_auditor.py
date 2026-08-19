from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TOOL_USERS_CONSISTENCY_AUDITOR_V1 = "users.consistency_auditor.run.v1"


class UserConsistencyCheck(StrEnum):
    DUPLICATE_NORMALIZED_EMAIL = "duplicate_normalized_email"
    INVALID_DISPLAY_NAME_LENGTH = "invalid_display_name_length"
    CREATED_AT_IN_FUTURE = "created_at_in_future"
    UPDATED_BEFORE_CREATED = "updated_before_created"
    STATUS_DEACTIVATION_MISMATCH = "status_deactivation_mismatch"
    VERIFIED_BEFORE_CREATED = "verified_before_created"
    LAST_LOGIN_BEFORE_CREATED = "last_login_before_created"


class ConsistencySeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConsistencyToolResultCode(StrEnum):
    OK = "ok"
    ISSUES_FOUND = "issues_found"
    FAILED = "failed"


class UserConsistencyAuditorInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID | None = None
    checks: list[UserConsistencyCheck] | None = None
    limit_per_check: int = Field(default=100, ge=1, le=500)
    now_utc: datetime | None = None


class UserConsistencyFindingV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    severity: ConsistencySeverity
    user_id: UUID | None
    message: str
    evidence: dict[str, object]


class UserConsistencySeverityTotalsV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class UserConsistencyAuditorOutputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = TOOL_USERS_CONSISTENCY_AUDITOR_V1
    run_id: UUID
    result_code: ConsistencyToolResultCode
    generated_at_utc: datetime
    total_users: int
    checks_executed: int
    issues_total: int
    issues_by_severity: UserConsistencySeverityTotalsV1
    findings: list[UserConsistencyFindingV1]