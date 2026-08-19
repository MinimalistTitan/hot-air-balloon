from uuid import uuid4

from app.modules.user.domain.authorization import (
    AuthorizationContext,
    Permission,
    RoleName,
    role_definition,
)


def test_each_selected_role_has_a_definition() -> None:
    assert {
        role_definition(role).name
        for role in RoleName
    } == set(RoleName)


def test_read_only_analyst_has_reads_but_no_mutations() -> None:
    context = AuthorizationContext(
        user_id=uuid4(),
        roles=frozenset({RoleName.READ_ONLY_ANALYST}),
        site_codes=frozenset({"HN-01"}),
    )

    assert context.can(Permission.WORK_ORDERS_READ, site_code="HN-01")
    assert context.can(Permission.REPORTS_READ, site_code="HN-01")
    assert not context.can(Permission.WORK_ORDERS_UPDATE, site_code="HN-01")
    assert not context.can(Permission.WORK_ORDERS_READ, site_code="HN-02")


def test_multiple_roles_union_permissions_and_administrator_is_global() -> None:
    context = AuthorizationContext(
        user_id=uuid4(),
        roles=frozenset(
            {
                RoleName.MAINTENANCE_TECHNICIAN,
                RoleName.MAINTENANCE_SUPERVISOR,
            }
        ),
        site_codes=frozenset({"HN-01"}),
    )
    administrator = AuthorizationContext(
        user_id=uuid4(),
        roles=frozenset({RoleName.SYSTEM_ADMINISTRATOR}),
        global_scope=True,
    )

    assert context.can(Permission.WORK_ORDERS_COMPLETE, site_code="HN-01")
    assert administrator.can(Permission.ROLES_MANAGE, site_code="HN-99")