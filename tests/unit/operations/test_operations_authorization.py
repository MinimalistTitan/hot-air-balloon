from uuid import uuid4

import pytest

from app.modules.user.application.authorization_policy import (
    AuthorizationPolicy,
    AuthorizationPolicyError,
)
from app.modules.user.domain.authorization import Permission, RoleName


class FakeUserRepository:
    def __init__(self) -> None:
        self.user_roles: dict[str, frozenset[str]] = {}
        self.user_sites: dict[str, frozenset[str]] = {}

    async def get_user_roles(self, user_id_str: str) -> frozenset[str]:
        return self.user_roles.get(str(user_id_str), frozenset())

    async def get_user_sites(self, user_id_str: str) -> frozenset[str]:
        return self.user_sites.get(str(user_id_str), frozenset())


@pytest.mark.asyncio
async def test_maintenance_technician_can_update_work_order() -> None:
    """Maintenance technician can update work order status within allowed transitions."""
    user_repo = FakeUserRepository()
    policy = AuthorizationPolicy(user_repo)  # type: ignore

    user_id = uuid4()
    user_repo.user_roles[str(user_id)] = frozenset({RoleName.MAINTENANCE_TECHNICIAN})
    user_repo.user_sites[str(user_id)] = frozenset({"HN-01"})

    # Technician has permission to change status
    await policy.require_permission(
        user_id,
        Permission.WORK_ORDERS_CHANGE_STATUS,
        site_code="HN-01",
    )


@pytest.mark.asyncio
async def test_read_only_analyst_cannot_update_work_order() -> None:
    """Read-only analyst cannot update work orders."""
    user_repo = FakeUserRepository()
    policy = AuthorizationPolicy(user_repo)  # type: ignore

    user_id = uuid4()
    user_repo.user_roles[str(user_id)] = frozenset({RoleName.READ_ONLY_ANALYST})
    user_repo.user_sites[str(user_id)] = frozenset({"HN-01"})

    # Read-only analyst lacks permission to update
    with pytest.raises(AuthorizationPolicyError):
        await policy.require_permission(
            user_id,
            Permission.WORK_ORDERS_UPDATE,
            site_code="HN-01",
        )


@pytest.mark.asyncio
async def test_maintenance_supervisor_can_complete_work_order() -> None:
    """Maintenance supervisor can complete work orders."""
    user_repo = FakeUserRepository()
    policy = AuthorizationPolicy(user_repo)  # type: ignore

    user_id = uuid4()
    user_repo.user_roles[str(user_id)] = frozenset({RoleName.MAINTENANCE_SUPERVISOR})
    user_repo.user_sites[str(user_id)] = frozenset({"HN-01"})

    # Supervisor has completion permission
    await policy.require_permission(
        user_id,
        Permission.WORK_ORDERS_COMPLETE,
        site_code="HN-01",
    )


@pytest.mark.asyncio
async def test_technician_cannot_complete_work_order_without_supervisor() -> None:
    """Maintenance technician cannot complete work orders (supervisor approval required)."""
    user_repo = FakeUserRepository()
    policy = AuthorizationPolicy(user_repo)  # type: ignore

    user_id = uuid4()
    user_repo.user_roles[str(user_id)] = frozenset({RoleName.MAINTENANCE_TECHNICIAN})
    user_repo.user_sites[str(user_id)] = frozenset({"HN-01"})

    # Technician lacks completion permission
    with pytest.raises(AuthorizationPolicyError):
        await policy.require_permission(
            user_id,
            Permission.WORK_ORDERS_COMPLETE,
            site_code="HN-01",
        )


@pytest.mark.asyncio
async def test_cross_site_access_denied() -> None:
    """User cannot access work orders outside assigned sites."""
    user_repo = FakeUserRepository()
    policy = AuthorizationPolicy(user_repo)  # type: ignore

    user_id = uuid4()
    user_repo.user_roles[str(user_id)] = frozenset({RoleName.MAINTENANCE_TECHNICIAN})
    user_repo.user_sites[str(user_id)] = frozenset({"HN-01"})  # Only HN-01

    # Technician lacks access to HN-02
    with pytest.raises(AuthorizationPolicyError):
        await policy.require_permission(
            user_id,
            Permission.WORK_ORDERS_READ,
            site_code="HN-02",  # Different site
        )


@pytest.mark.asyncio
async def test_administrator_has_unrestricted_access() -> None:
    """System administrator can access any site and perform any action."""
    user_repo = FakeUserRepository()
    policy = AuthorizationPolicy(user_repo)  # type: ignore

    user_id = uuid4()
    user_repo.user_roles[str(user_id)] = frozenset({RoleName.SYSTEM_ADMINISTRATOR})

    # Admin can access any site with any permission
    await policy.require_permission(
        user_id,
        Permission.WORK_ORDERS_COMPLETE,
        site_code="any-site",
    )
    await policy.require_permission(
        user_id,
        Permission.ROLES_MANAGE,
        site_code="any-other-site",
    )
