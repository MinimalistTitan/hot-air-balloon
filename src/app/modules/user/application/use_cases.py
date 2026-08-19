from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.modules.user.application.dto import UserDTO
from app.modules.user.application.ports import (
    ConsistencyIssue,
    UserRepository,
    UserUnitOfWorkFactory,
)
from app.modules.user.domain.entities import User
from app.modules.user.domain.errors import EmailAlreadyRegisteredError, UserNotFoundError

type AuditCheck = Callable[
    [UserRepository],
    Awaitable[list[ConsistencyIssue]]
]

@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    email: str
    display_name: str
    source_system: str = "unknown"

@dataclass(slots=True)
class RegisterUser:
    unit_of_work_factory: UserUnitOfWorkFactory

    async def execute(self, command: RegisterUserCommand) -> UserDTO:
        user = User.register(
                                email=command.email, 
                                display_name=command.display_name,
                                source_system=command.source_system
                            )
        async with self.unit_of_work_factory() as unit_of_work:
            if await unit_of_work.users.get_by_email(user.email):
                raise EmailAlreadyRegisteredError(command.email)

            await unit_of_work.users.add(user)
            await unit_of_work.commit()

        return UserDTO.from_entity(user)


@dataclass(slots=True)
class GetUser:
    unit_of_work_factory: UserUnitOfWorkFactory

    async def execute(self, user_id: UUID) -> UserDTO:
        async with self.unit_of_work_factory() as unit_of_work:
            user = await unit_of_work.users.get_by_id(user_id)
            if user is None:
                raise UserNotFoundError(str(user_id))
        return UserDTO.from_entity(user)
    
    
@dataclass(frozen=True, slots=True)
class UserConsistencyAuditCommand:
    checks: tuple[str, ...] | None = None
    limit_per_check: int = 100
    run_id: UUID | None = None
    now_utc: datetime | None = None
    
@dataclass(frozen=True, slots=True)
class UserConsistencyAuditReport:
    run_id: UUID
    generated_at_utc: datetime
    total_users: int
    checks_executed: int
    issues_total: int
    result_code: str
    findings: list[ConsistencyIssue]
    
@dataclass(slots=True)
class RunUserConsistencyAudit:
    unit_of_work_factory: UserUnitOfWorkFactory
    
    async def execute(self, command: UserConsistencyAuditCommand) -> UserConsistencyAuditReport:
        now_utc = command.now_utc or datetime.now(UTC)
        run_id = command.run_id or uuid4()
        limit = min(max(command.limit_per_check, 1), 500)

        all_checks: list[tuple[str, AuditCheck]] = [
            ("duplicate_normalized_email", lambda repo: repo.find_duplicate_normalized_email(limit)),
            ("invalid_display_name_length", lambda repo: repo.find_invalid_display_name_length(limit)),
            ("created_at_in_future", lambda repo: repo.find_created_at_in_future(now_utc, limit)),
            ("updated_before_created", lambda repo: repo.find_updated_before_created(limit)),
            ("status_deactivation_mismatch", lambda repo: repo.find_status_deactivation_mismatch(limit)),
            ("verified_before_created", lambda repo: repo.find_verified_before_created(limit)),
            ("last_login_before_created", lambda repo: repo.find_last_login_before_created(limit)),
        ]

        selected = set(command.checks) if command.checks else None
        findings: list[ConsistencyIssue] = []

        async with self.unit_of_work_factory() as unit_of_work:
            total_users = await unit_of_work.users.count_total()

            for check_id, handler in all_checks:
                if selected is not None and check_id not in selected:
                    continue
                findings.extend(await handler(unit_of_work.users))

        findings.sort(
            key=lambda x: (
                x.check_id,
                str(x.user_id) if x.user_id else "",
                x.message,
            )
        )
        
        result_code = "issues_found" if findings else "ok"

        return UserConsistencyAuditReport(
            run_id=run_id,
            generated_at_utc=now_utc,
            total_users=total_users,
            checks_executed=len(all_checks) if selected is None else len(selected),
            issues_total=len(findings),
            result_code=result_code,
            findings=findings,
        )

