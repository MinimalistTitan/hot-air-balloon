from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.user.domain.entities import User


@dataclass(frozen=True, slots=True)
class UserDTO:
    id: UUID
    email: str
    display_name: str
    created_at: datetime
    source_system: str | None

    @classmethod
    def from_entity(cls, user: User) -> UserDTO:
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            created_at=user.created_at,
            source_system=user.source_system,
        )
