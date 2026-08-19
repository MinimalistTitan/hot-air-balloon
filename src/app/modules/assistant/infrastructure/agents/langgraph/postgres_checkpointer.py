from dataclasses import dataclass, field
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


@dataclass(slots=True)
class PostgresCheckpointer:
    """Owns the official LangGraph PostgreSQL saver and its connection pool."""

    database_url: str
    _pool: AsyncConnectionPool[AsyncConnection[dict[str, Any]]] = field(
        init=False,
        repr=False,
    )
    _saver: AsyncPostgresSaver | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        connection_string = self.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        self._pool = AsyncConnectionPool(
            conninfo=connection_string,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
            open=False,
        )

    @property
    def saver(self) -> AsyncPostgresSaver:
        if self._saver is None:
            raise RuntimeError("PostgresCheckpointer has not been started")
        return self._saver

    async def start(self) -> None:
        await self._pool.open()
        self._saver = AsyncPostgresSaver(self._pool)
        await self._saver.setup()

    async def stop(self) -> None:
        await self._pool.close()
        self._saver = None