from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from email_validator import EmailNotValidError, validate_email

from app.modules.user.domain.errors import InvalidDisplayNameError, InvalidEmailError


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"

@dataclass(frozen=True, slots=True, kw_only=True)
class User:
    id: UUID
    email: str
    display_name: str
    created_at: datetime
    status: UserStatus
    updated_at: datetime
    email_verified_at: datetime | None = None
    last_login_at: datetime | None = None
    deactivated_at: datetime | None = None
    source_system: str | None = None

    @classmethod
    def register(
        cls,
        *,
        email: str,
        display_name: str,
        source_system: str | None,
        user_id: UUID | None = None,
        now: datetime | None = None,
    ) -> User:
        try:
            normalized_email = validate_email(email.strip(), check_deliverability=False).normalized
        except EmailNotValidError as error:
            raise InvalidEmailError(str(error)) from error

        normalized_name = " ".join(display_name.split())
        if not 2 <= len(normalized_name) <= 100:
            msg = "Display name must contain between 2 and 100 characters"
            raise InvalidDisplayNameError(msg)

        return cls(
            id=user_id or uuid4(),
            email=normalized_email,
            display_name=normalized_name,
            created_at=now or datetime.now(UTC),
            status=UserStatus.ACTIVE,
            updated_at=now or datetime.now(UTC),
            email_verified_at=None,
            last_login_at=None,
            deactivated_at=None,
            source_system=source_system,
        )
