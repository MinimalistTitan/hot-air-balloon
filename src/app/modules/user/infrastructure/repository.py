
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.user.application.ports import ConsistencyIssue
from app.modules.user.contracts.consistency_auditor import ConsistencySeverity
from app.modules.user.domain.entities import User
from app.modules.user.domain.errors import EmailAlreadyRegisteredError
from app.modules.user.infrastructure.models import UserRecord, UserRoleRecord, UserSiteRecord


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        record = await self._session.get(UserRecord, user_id)
        return record.to_entity() if record else None

    async def get_by_email(self, email: str) -> User | None:
        statement = select(UserRecord).where(UserRecord.email == email)
        record = await self._session.scalar(statement)
        return record.to_entity() if record else None

    async def add(self, user: User) -> None:
        self._session.add(UserRecord.from_entity(user))
        try:
            await self._session.flush()
        except IntegrityError as error:
            await self._session.rollback()
            raise EmailAlreadyRegisteredError(user.email) from error
        
        
    async def count_total(self) -> int:
        statement = select(func.count()).select_from(UserRecord)
        total = await self._session.scalar(statement)
        return int(total or 0)


    async def find_duplicate_normalized_email(self, limit: int) -> list[ConsistencyIssue]:
        normalized_email = func.lower(func.trim(UserRecord.email))
        
        statement = (
            select(normalized_email.label("n_email"), func.count().label("occurrences"))
            .group_by(normalized_email)
            .having(func.count() > 1)
            .order_by(func.count().desc(), normalized_email.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(statement)).all()
        
        return [
            ConsistencyIssue(
                check_id="duplicate_normalized_email",
                severity=ConsistencySeverity.HIGH,
                user_id=None,
                message="Multiple rows share normalized email",
                evidence={"normalized_email": row.n_email, "occurrences": int(row.occurrences)},
            )
            for row in rows
        ]


    async def find_invalid_display_name_length(self, limit: int) -> list[ConsistencyIssue]:
        trimmed_len = func.length(func.trim(UserRecord.display_name))
        
        statement = (
            select(UserRecord.id, UserRecord.display_name)
            .where(or_(trimmed_len < 3, trimmed_len > 100))
            .order_by(UserRecord.created_at.asc(), UserRecord.id.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(statement)).all()
        return [
            ConsistencyIssue(
                check_id="invalid_display_name_length",
                severity=ConsistencySeverity.MEDIUM,
                user_id=row.id,
                message="Display name length outside allowed range",
                evidence={"display_name": row.display_name, "length": len(row.display_name.strip())},
            )
            for row in rows
        ]

    async def find_created_at_in_future(self, now_utc: datetime, limit: int) -> list[ConsistencyIssue]:
        statement = (
            select(UserRecord.id, UserRecord.created_at)
            .where(UserRecord.created_at > now_utc)
            .order_by(UserRecord.created_at.desc(), UserRecord.id.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(statement)).all()
        return [
            ConsistencyIssue(
                check_id="created_at_in_future",
                severity=ConsistencySeverity.HIGH,
                user_id=row.id,
                message="created_at is in the future",
                evidence={"created_at": row.created_at.isoformat(), "now_utc": now_utc.isoformat()},
            )
            for row in rows
        ]

    async def find_updated_before_created(self, limit: int) -> list[ConsistencyIssue]:
        statement = (
            select(UserRecord.id, UserRecord.created_at, UserRecord.updated_at)
            .where(UserRecord.updated_at < UserRecord.created_at)
            .order_by(UserRecord.updated_at.asc(), UserRecord.id.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(statement)).all()
        return [
            ConsistencyIssue(
            check_id="updated_before_created",
            severity=ConsistencySeverity.HIGH,
            user_id=row.id,
            message="updated_at earlier than created_at",
            evidence={"created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()},
            )
            for row in rows
        ]

    async def find_status_deactivation_mismatch(self, limit: int) -> list[ConsistencyIssue]:
        statement = (
            select(UserRecord.id, UserRecord.status, UserRecord.deactivated_at)
            .where(
                or_(
                    and_(UserRecord.status == "active", UserRecord.deactivated_at.is_not(None)),
                    and_(UserRecord.status != "active", UserRecord.deactivated_at.is_(None)),
                    )
                )
                .order_by(UserRecord.created_at.asc(), UserRecord.id.asc())
                .limit(limit)
        )
        
        rows = (await self._session.execute(statement)).all()
        
        return [
            ConsistencyIssue(
                check_id="status_deactivation_mismatch",
                severity=ConsistencySeverity.MEDIUM,
                user_id=row.id,
                message="status and deactivated_at are inconsistent",
                evidence={
                    "status": row.status,
                    "deactivated_at": row.deactivated_at.isoformat() if row.deactivated_at else None,
                },
            )
            for row in rows
        ]

    async def find_verified_before_created(self, limit: int) -> list[ConsistencyIssue]:
        statement = (
            select(UserRecord.id, UserRecord.created_at, UserRecord.email_verified_at)
            .where(UserRecord.email_verified_at.is_not(None), UserRecord.email_verified_at < UserRecord.created_at)
            .order_by(UserRecord.email_verified_at.asc(), UserRecord.id.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(statement)).all()
        return [
            ConsistencyIssue(
                check_id="verified_before_created",
                severity=ConsistencySeverity.MEDIUM,
                user_id=row.id,
                message="email_verified_at earlier than created_at",
                evidence={
                "created_at": row.created_at.isoformat(),
                "email_verified_at": row.email_verified_at.isoformat() if row.email_verified_at else None,
                },
            )
            for row in rows
        ]

    async def find_last_login_before_created(self, limit: int) -> list[ConsistencyIssue]:
        statement = (
            select(UserRecord.id, UserRecord.created_at, UserRecord.last_login_at)
            .where(UserRecord.last_login_at.is_not(None), UserRecord.last_login_at < UserRecord.created_at)
            .order_by(UserRecord.last_login_at.asc(), UserRecord.id.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(statement)).all()
        return [
            ConsistencyIssue(
                check_id="last_login_before_created",
                severity=ConsistencySeverity.LOW,
                user_id=row.id,
                message="last_login_at earlier than created_at",
                evidence={
                    "created_at": row.created_at.isoformat(),
                    "last_login_at": row.last_login_at.isoformat() if row.last_login_at else None,
                },
            )
            for row in rows
        ]

    async def get_user_roles(self, user_id: UUID) -> frozenset[str]:
        """Load the role names assigned to a user."""
        statement = select(UserRoleRecord.role_name).where(UserRoleRecord.user_id == user_id)
        rows = (await self._session.execute(statement)).scalars().all()
        return frozenset(rows)

    async def get_user_sites(self, user_id: UUID) -> frozenset[str]:
        """Load the site codes assigned to a user."""
        statement = select(UserSiteRecord.site_code).where(UserSiteRecord.user_id == user_id)
        rows = (await self._session.execute(statement)).scalars().all()
        return frozenset(rows)

    async def assign_role(self, user_id: UUID, role_name: str) -> None:
        """Assign a role to a user."""
        self._session.add(UserRoleRecord(user_id=user_id, role_name=role_name))
        try:
            await self._session.flush()
        except IntegrityError as error:
            await self._session.rollback()
            raise error

    async def remove_role(self, user_id: UUID, role_name: str) -> None:
        """Remove a role assignment from a user."""
        statement = select(UserRoleRecord).where(
            and_(UserRoleRecord.user_id == user_id, UserRoleRecord.role_name == role_name)
        )
        record = await self._session.scalar(statement)
        if record:
            await self._session.delete(record)
            await self._session.flush()

    async def assign_site(self, user_id: UUID, site_code: str) -> None:
        """Assign a site to a user."""
        self._session.add(UserSiteRecord(user_id=user_id, site_code=site_code))
        try:
            await self._session.flush()
        except IntegrityError as error:
            await self._session.rollback()
            raise error

    async def remove_site(self, user_id: UUID, site_code: str) -> None:
        """Remove a site assignment from a user."""
        statement = select(UserSiteRecord).where(
            and_(UserSiteRecord.user_id == user_id, UserSiteRecord.site_code == site_code)
        )
        record = await self._session.scalar(statement)
        if record:
            await self._session.delete(record)
            await self._session.flush()
