from types import TracebackType
from typing import Self

from app.core.database.database import SessionFactory
from app.modules.user.infrastructure.repository import UserRepository


class UserUnitOfWork:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session = session_factory()
        self.users = UserRepository(self._session)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self._session.rollback()
        await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()
