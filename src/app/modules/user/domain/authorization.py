from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Permission(StrEnum):
    USERS_MANAGE = "users:manage"
    ROLES_MANAGE = "roles:manage"
    WORK_ORDERS_READ = "work_orders:read"
    WORK_ORDERS_UPDATE = "work_orders:update"
    WORK_ORDERS_CHANGE_STATUS = "work_orders:change_status"
    WORK_ORDERS_COMPLETE = "work_orders:complete"
    WORK_ORDERS_CANCEL = "work_orders:cancel"
    MAINTENANCE_TICKETS_READ = "maintenance_tickets:read"
    MAINTENANCE_TICKETS_UPDATE = "maintenance_tickets:update"
    ASSETS_READ = "assets:read"
    ASSETS_UPDATE = "assets:update"
    SPARE_PARTS_READ = "spare_parts:read"
    SPARE_PARTS_ISSUE = "spare_parts:issue"
    SPARE_PARTS_ADJUST_INVENTORY = "spare_parts:adjust_inventory"
    PRODUCTION_SCHEDULE_READ = "production_schedule:read"
    PRODUCTION_SCHEDULE_UPDATE = "production_schedule:update"
    PRODUCTION_SCHEDULE_PUBLISH = "production_schedule:publish"
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_UPLOAD = "documents:upload"
    DOCUMENTS_DELETE = "documents:delete"
    REPORTS_READ = "reports:read"
    AUDIT_LOGS_READ = "audit_logs:read"
    WEB_SEARCH = "web_search"


class RoleName(StrEnum):
    SYSTEM_ADMINISTRATOR = "system_administrator"
    OPERATIONS_MANAGER = "operations_manager"
    READ_ONLY_ANALYST = "read_only_analyst"
    MAINTENANCE_TECHNICIAN = "maintenance_technician"
    MAINTENANCE_SUPERVISOR = "maintenance_supervisor"


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    name: RoleName
    permissions: frozenset[Permission]


_READ_OPERATIONS: frozenset[Permission] = frozenset(
    {
        Permission.WORK_ORDERS_READ,
        Permission.MAINTENANCE_TICKETS_READ,
        Permission.ASSETS_READ,
        Permission.SPARE_PARTS_READ,
        Permission.PRODUCTION_SCHEDULE_READ,
    }
)

ROLE_DEFINITIONS: dict[RoleName, RoleDefinition] = {
    RoleName.SYSTEM_ADMINISTRATOR: RoleDefinition(
        name=RoleName.SYSTEM_ADMINISTRATOR,
        permissions=frozenset(Permission),
    ),
    RoleName.OPERATIONS_MANAGER: RoleDefinition(
        name=RoleName.OPERATIONS_MANAGER,
        permissions=_READ_OPERATIONS
        | frozenset(
            {
                Permission.WORK_ORDERS_UPDATE,
                Permission.WORK_ORDERS_CHANGE_STATUS,
                Permission.WORK_ORDERS_COMPLETE,
                Permission.WORK_ORDERS_CANCEL,
                Permission.MAINTENANCE_TICKETS_UPDATE,
                Permission.PRODUCTION_SCHEDULE_UPDATE,
                Permission.PRODUCTION_SCHEDULE_PUBLISH,
                Permission.DOCUMENTS_READ,
                Permission.DOCUMENTS_UPLOAD,
                Permission.REPORTS_READ,
                Permission.AUDIT_LOGS_READ,
                Permission.WEB_SEARCH,
            }
        ),
    ),
    RoleName.READ_ONLY_ANALYST: RoleDefinition(
        name=RoleName.READ_ONLY_ANALYST,
        permissions=_READ_OPERATIONS
        | frozenset(
            {
                Permission.DOCUMENTS_READ,
                Permission.REPORTS_READ,
                Permission.AUDIT_LOGS_READ,
                Permission.WEB_SEARCH,
            }
        ),
    ),
    RoleName.MAINTENANCE_TECHNICIAN: RoleDefinition(
        name=RoleName.MAINTENANCE_TECHNICIAN,
        permissions=frozenset(
            {
                Permission.WORK_ORDERS_READ,
                Permission.WORK_ORDERS_UPDATE,
                Permission.WORK_ORDERS_CHANGE_STATUS,
                Permission.MAINTENANCE_TICKETS_READ,
                Permission.MAINTENANCE_TICKETS_UPDATE,
                Permission.ASSETS_READ,
                Permission.SPARE_PARTS_READ,
                Permission.SPARE_PARTS_ISSUE,
                Permission.DOCUMENTS_READ,
                Permission.DOCUMENTS_UPLOAD,
                Permission.WEB_SEARCH,
            }
        ),
    ),
    RoleName.MAINTENANCE_SUPERVISOR: RoleDefinition(
        name=RoleName.MAINTENANCE_SUPERVISOR,
        permissions=frozenset(
            {
                Permission.WORK_ORDERS_READ,
                Permission.WORK_ORDERS_UPDATE,
                Permission.WORK_ORDERS_CHANGE_STATUS,
                Permission.WORK_ORDERS_COMPLETE,
                Permission.WORK_ORDERS_CANCEL,
                Permission.MAINTENANCE_TICKETS_READ,
                Permission.MAINTENANCE_TICKETS_UPDATE,
                Permission.ASSETS_READ,
                Permission.SPARE_PARTS_READ,
                Permission.SPARE_PARTS_ISSUE,
                Permission.DOCUMENTS_READ,
                Permission.DOCUMENTS_UPLOAD,
                Permission.REPORTS_READ,
                Permission.WEB_SEARCH,
            }
        ),
    ),
}


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    user_id: UUID
    roles: frozenset[RoleName]
    site_codes: frozenset[str] = frozenset()
    global_scope: bool = False

    @property
    def permissions(self) -> frozenset[Permission]:
        return frozenset(
            permission
            for role in self.roles
            for permission in ROLE_DEFINITIONS[role].permissions
        )

    def can(self, permission: Permission, *, site_code: str | None = None) -> bool:
        if permission not in self.permissions:
            return False
        return site_code is None or self.global_scope or site_code in self.site_codes


def role_definition(role: RoleName) -> RoleDefinition:
    return ROLE_DEFINITIONS[role]