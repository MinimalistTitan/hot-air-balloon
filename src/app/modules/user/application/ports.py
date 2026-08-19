from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Any, Protocol, Self
from uuid import UUID

from attr import dataclass

from app.modules.user.contracts.consistency_auditor import ConsistencySeverity
from app.modules.user.domain.entities import User


@dataclass(frozen=True, slots=True)
class ConsistencyIssue:
    check_id: str
    severity: ConsistencySeverity
    user_id: UUID | None
    message: str
    evidence: dict[str, Any]

class UserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def add(self, user: User) -> None: ...
    
    
    async def count_total(self) -> int: ...
    async def find_duplicate_normalized_email(self, limit: int) -> list[ConsistencyIssue]: ...
    async def find_invalid_display_name_length(self, limit: int) -> list[ConsistencyIssue]: ...
    async def find_created_at_in_future(self, now_utc: datetime, limit: int) -> list[ConsistencyIssue]: ...
    async def find_updated_before_created(self, limit: int) -> list[ConsistencyIssue]: ...
    async def find_status_deactivation_mismatch(self, limit: int) -> list[ConsistencyIssue]: ...
    async def find_verified_before_created(self, limit: int) -> list[ConsistencyIssue]: ...
    async def find_last_login_before_created(self, limit: int) -> list[ConsistencyIssue]: ...


class UnitOfWork(Protocol):
    @property
    def users(self) -> UserRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


type UserUnitOfWorkFactory = Callable[[], UnitOfWork]
