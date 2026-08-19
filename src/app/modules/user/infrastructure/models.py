from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base
from app.core.sqlalchemy_types import UTCDateTime
from app.modules.user.domain.entities import User, UserStatus


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    source_system: Mapped[str | None] = mapped_column(String(50), nullable=True)

    @classmethod
    def from_entity(cls, user: User) -> UserRecord:
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            created_at=user.created_at,
            status=user.status,
            updated_at=user.updated_at,
            email_verified_at=user.email_verified_at,
            last_login_at=user.last_login_at,
            deactivated_at=user.deactivated_at,
            source_system=user.source_system,
        )

    def to_entity(self) -> User:
        return User(
            id=self.id,
            email=self.email,
            display_name=self.display_name,
            created_at=self.created_at,
            status=UserStatus(self.status),
            updated_at=self.updated_at,
            email_verified_at=self.email_verified_at,
            last_login_at=self.last_login_at,
            deactivated_at=self.deactivated_at,
            source_system=self.source_system,
        )


class RoleRecord(Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)


class UserRoleRecord(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", name="fk_user_roles_user_id_users"), primary_key=True
    )
    role_name: Mapped[str] = mapped_column(
        ForeignKey("roles.name", name="fk_user_roles_role_name_roles"), primary_key=True
    )


class UserSiteRecord(Base):
    __tablename__ = "user_sites"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", name="fk_user_sites_user_id_users"), primary_key=True
    )
    site_code: Mapped[str] = mapped_column(
        ForeignKey("sites.code", name="fk_user_sites_site_code_sites"), primary_key=True
    )
