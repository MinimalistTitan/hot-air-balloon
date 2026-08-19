from __future__ import annotations

from typing import Protocol

from app.modules.user.domain.authorization import AuthorizationContext, Permission


class PermissionChecker(Protocol):
    async def can_call(
        self,
        authorization_context: AuthorizationContext,
        permission: Permission,
        *,
        site_code: str | None = None,
    ) -> bool: ...


class DefaultPermissionChecker:
    async def can_call(
        self,
        authorization_context: AuthorizationContext,
        permission: Permission,
        *,
        site_code: str | None = None,
    ) -> bool:
        return authorization_context.can(permission, site_code=site_code)