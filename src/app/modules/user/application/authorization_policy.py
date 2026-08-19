from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.user.domain.authorization import AuthorizationContext, Permission, RoleName
from app.modules.user.infrastructure.repository import UserRepository


class AuthorizationPolicyError(Exception):
    """Raised when a principal lacks required authorization."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class AuthorizationPolicy:
    """Enforces authorization checks at the application boundary."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def get_authorization_context(
        self,
        user_id: UUID,
    ) -> AuthorizationContext:
        """Load and build the authorization context for a user."""
        roles = await self._repository.get_user_roles(user_id)
        sites = await self._repository.get_user_sites(user_id)

        # System Administrator has global scope
        global_scope = RoleName.SYSTEM_ADMINISTRATOR in roles

        return AuthorizationContext(
            user_id=user_id,
            roles=frozenset(roles),  # type: ignore
            site_codes=sites,
            global_scope=global_scope,
        )

    async def require_permission(
        self,
        user_id: UUID,
        permission: Permission,
        *,
        site_code: str | None = None,
    ) -> None:
        """Check that a user has a required permission, raise if denied."""
        context = await self.get_authorization_context(user_id)
        if not context.can(permission, site_code=site_code):
            raise AuthorizationPolicyError(
                f"User {user_id} lacks permission {permission.value}"
                + (f" for site {site_code}" if site_code else "")
            )

    async def require_any_permission(
        self,
        user_id: UUID,
        permissions: frozenset[Permission],
        *,
        site_code: str | None = None,
    ) -> None:
        """Check that a user has at least one permission in the set."""
        context = await self.get_authorization_context(user_id)
        if not any(context.can(p, site_code=site_code) for p in permissions):
            raise AuthorizationPolicyError(
                f"User {user_id} lacks at least one of {len(permissions)} required permissions"
                + (f" for site {site_code}" if site_code else "")
            )
