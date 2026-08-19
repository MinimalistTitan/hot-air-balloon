from uuid import uuid4

import pytest

from app.modules.user.application.authorization_policy import (
    AuthorizationPolicy,
    AuthorizationPolicyError,
)
from app.modules.user.domain.authorization import (
    AuthorizationContext,
    Permission,
    RoleName,
)


class FakeUserRepository:
    def __init__(self) -> None:
        self.user_roles: dict[str, frozenset[str]] = {}
        self.user_sites: dict[str, frozenset[str]] = {}

    async def get_user_roles(self, user_id_str: str) -> frozenset[str]:
        return self.user_roles.get(str(user_id_str), frozenset())

    async def get_user_sites(self, user_id_str: str) -> frozenset[str]:
        return self.user_sites.get(str(user_id_str), frozenset())


@pytest.mark.asyncio
async def test_authorization_context_loading() -> None:
    repository = FakeUserRepository()
    policy = AuthorizationPolicy(repository)  # type: ignore

    user_id = uuid4()
    user_id_str = str(user_id)
    repository.user_roles[user_id_str] = frozenset({"read_only_analyst"})
    repository.user_sites[user_id_str] = frozenset({"HN-01"})

    context = await policy.get_authorization_context(user_id)
    assert context.user_id == user_id
    assert RoleName.READ_ONLY_ANALYST in context.roles
    assert "HN-01" in context.site_codes
    assert not context.global_scope


@pytest.mark.asyncio
async def test_administrator_has_global_scope() -> None:
    repository = FakeUserRepository()
    policy = AuthorizationPolicy(repository)  # type: ignore

    user_id = uuid4()
    user_id_str = str(user_id)
    repository.user_roles[user_id_str] = frozenset({"system_administrator"})

    context = await policy.get_authorization_context(user_id)
    assert context.global_scope
    assert context.can(Permission.ROLES_MANAGE, site_code="any-site")


@pytest.mark.asyncio
async def test_require_permission_success() -> None:
    repository = FakeUserRepository()
    policy = AuthorizationPolicy(repository)  # type: ignore

    user_id = uuid4()
    user_id_str = str(user_id)
    repository.user_roles[user_id_str] = frozenset({"read_only_analyst"})
    repository.user_sites[user_id_str] = frozenset({"HN-01"})

    # Should not raise
    await policy.require_permission(
        user_id,
        Permission.WORK_ORDERS_READ,
        site_code="HN-01",
    )


@pytest.mark.asyncio
async def test_require_permission_denied_no_permission() -> None:
    repository = FakeUserRepository()
    policy = AuthorizationPolicy(repository)  # type: ignore

    user_id = uuid4()
    user_id_str = str(user_id)
    repository.user_roles[user_id_str] = frozenset({"read_only_analyst"})
    repository.user_sites[user_id_str] = frozenset({"HN-01"})

    with pytest.raises(AuthorizationPolicyError) as exc_info:
        await policy.require_permission(
            user_id,
            Permission.WORK_ORDERS_UPDATE,
            site_code="HN-01",
        )
    assert "lacks permission" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_require_permission_denied_wrong_site() -> None:
    repository = FakeUserRepository()
    policy = AuthorizationPolicy(repository)  # type: ignore

    user_id = uuid4()
    user_id_str = str(user_id)
    repository.user_roles[user_id_str] = frozenset({"read_only_analyst"})
    repository.user_sites[user_id_str] = frozenset({"HN-01"})

    with pytest.raises(AuthorizationPolicyError):
        await policy.require_permission(
            user_id,
            Permission.WORK_ORDERS_READ,
            site_code="HN-02",  # Different site
        )


@pytest.mark.asyncio
async def test_require_any_permission() -> None:
    repository = FakeUserRepository()
    policy = AuthorizationPolicy(repository)  # type: ignore

    user_id = uuid4()
    user_id_str = str(user_id)
    repository.user_roles[user_id_str] = frozenset({"read_only_analyst"})
    repository.user_sites[user_id_str] = frozenset({"HN-01"})

    # Read-only analyst has REPORTS_READ but not WORK_ORDERS_UPDATE
    await policy.require_any_permission(
        user_id,
        frozenset({Permission.WORK_ORDERS_UPDATE, Permission.REPORTS_READ}),
        site_code="HN-01",
    )
