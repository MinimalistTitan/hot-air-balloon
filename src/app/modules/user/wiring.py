from dataclasses import dataclass

from app.core.config import Environment, Settings
from app.core.database.database import SessionFactory
from app.modules.assistant.tool_gateway.domain import AssistantToolRegistration
from app.modules.user.application.ports import UserUnitOfWorkFactory
from app.modules.user.application.use_cases import GetUser, RegisterUser, RunUserConsistencyAudit
from app.modules.user.infrastructure.unit_of_work import UserUnitOfWork
from app.modules.user.infrastructure.tools import build_users_consistency_auditor_tool

@dataclass(frozen=True, slots=True)
class UsersModule:
    unit_of_work_factory: UserUnitOfWorkFactory
    register_user: RegisterUser
    get_user: GetUser
    consistency_audit: RunUserConsistencyAudit
    consistency_auditor_tool: AssistantToolRegistration
    audit_endpoint_enabled: bool

    @property
    def tools(self) -> tuple[AssistantToolRegistration, ...]:
        return (self.consistency_auditor_tool,)


def build_users_module(
    settings: Settings,
    session_factory: SessionFactory,
) -> UsersModule:
    def unit_of_work_factory() -> UserUnitOfWork:
        return UserUnitOfWork(session_factory)

    consistency_auditor_tool = build_users_consistency_auditor_tool(
        unit_of_work_factory=unit_of_work_factory
    )

    return UsersModule(
        unit_of_work_factory=unit_of_work_factory,
        register_user=RegisterUser(
            unit_of_work_factory=unit_of_work_factory,
        ),
        get_user=GetUser(
            unit_of_work_factory=unit_of_work_factory,
        ),
        consistency_audit=RunUserConsistencyAudit(
            unit_of_work_factory=unit_of_work_factory,
        ),
        consistency_auditor_tool=consistency_auditor_tool,
        audit_endpoint_enabled=settings.environment
        in {
            Environment.LOCAL,
            Environment.TEST,
        },
    )
