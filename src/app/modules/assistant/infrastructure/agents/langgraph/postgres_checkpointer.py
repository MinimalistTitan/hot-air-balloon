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
    _started: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.database_url.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("PostgresCheckpointer requires a PostgreSQL database URL")

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
        if self._started:
            return

        try:
            await self._pool.open(wait=True)
            saver = AsyncPostgresSaver(self._pool)
            await saver.setup()
        except BaseException as start_error:
            self._saver = None
            try:
                await self._pool.close()
            except BaseException as close_error:
                raise BaseExceptionGroup(
                    "Postgres checkpointer startup and cleanup failed",
                    [start_error, close_error],
                ) from start_error
            raise

        self._saver = saver
        self._started = True

    async def stop(self) -> None:
        if not self._started:
            return

        try:
            await self._pool.close()
        finally:
            self._saver = None
            self._started = False
