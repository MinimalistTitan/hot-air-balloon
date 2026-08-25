from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.database.database import Base, create_session_factory
from app.modules.operations.infrastructure.manufacturing_maintenance.models.models import (
    SiteRecord,
)
from app.modules.user.infrastructure.models import (
    RoleRecord,
    UserRecord,
    UserRoleRecord,
    UserSiteRecord,
)

# Keep references to all models needed by the user repository schema. Importing
# them registers their tables in Base.metadata before the schema is created.
_REGISTERED_MODELS = (
    RoleRecord,
    SiteRecord,
    UserRecord,
    UserRoleRecord,
    UserSiteRecord,
)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Create an isolated in-memory SQLite session for a test."""
    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()
