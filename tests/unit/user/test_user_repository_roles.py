from uuid import uuid4

import pytest

from app.modules.user.domain.authorization import RoleName
from app.modules.user.domain.entities import User
from app.modules.user.infrastructure.repository import UserRepository
from tests.fixtures import get_session


@pytest.mark.asyncio
async def test_assign_and_get_user_roles() -> None:
    async with get_session() as session:
        repository = UserRepository(session)
        user_id = uuid4()
        user = User.register(
            email="test@example.com",
            display_name="Test User",
            source_system=None,
            user_id=user_id,
        )
        await repository.add(user)
        await session.commit()

        # Initially no roles
        roles = await repository.get_user_roles(user_id)
        assert roles == frozenset()

        # Assign role
        await repository.assign_role(user_id, "maintenance_technician")
        await session.commit()

        roles = await repository.get_user_roles(user_id)
        assert roles == frozenset({"maintenance_technician"})

        # Assign another role
        await repository.assign_role(user_id, "maintenance_supervisor")
        await session.commit()

        roles = await repository.get_user_roles(user_id)
        assert roles == frozenset({"maintenance_technician", "maintenance_supervisor"})


@pytest.mark.asyncio
async def test_assign_and_get_user_sites() -> None:
    async with get_session() as session:
        repository = UserRepository(session)
        user_id = uuid4()
        user = User.register(
            email="site_test@example.com",
            display_name="Site Test User",
            source_system=None,
            user_id=user_id,
        )
        await repository.add(user)
        await session.commit()

        # Initially no sites
        sites = await repository.get_user_sites(user_id)
        assert sites == frozenset()

        # Assign site
        await repository.assign_site(user_id, "HN-01")
        await session.commit()

        sites = await repository.get_user_sites(user_id)
        assert sites == frozenset({"HN-01"})

        # Assign another site
        await repository.assign_site(user_id, "HN-02")
        await session.commit()

        sites = await repository.get_user_sites(user_id)
        assert sites == frozenset({"HN-01", "HN-02"})


@pytest.mark.asyncio
async def test_remove_role() -> None:
    async with get_session() as session:
        repository = UserRepository(session)
        user_id = uuid4()
        user = User.register(
            email="remove_test@example.com",
            display_name="Remove Test User",
            source_system=None,
            user_id=user_id,
        )
        await repository.add(user)
        await repository.assign_role(user_id, "maintenance_technician")
        await session.commit()

        roles = await repository.get_user_roles(user_id)
        assert "maintenance_technician" in roles

        await repository.remove_role(user_id, "maintenance_technician")
        await session.commit()

        roles = await repository.get_user_roles(user_id)
        assert roles == frozenset()


@pytest.mark.asyncio
async def test_remove_site() -> None:
    async with get_session() as session:
        repository = UserRepository(session)
        user_id = uuid4()
        user = User.register(
            email="remove_site@example.com",
            display_name="Remove Site User",
            source_system=None,
            user_id=user_id,
        )
        await repository.add(user)
        await repository.assign_site(user_id, "HN-01")
        await session.commit()

        sites = await repository.get_user_sites(user_id)
        assert "HN-01" in sites

        await repository.remove_site(user_id, "HN-01")
        await session.commit()

        sites = await repository.get_user_sites(user_id)
        assert sites == frozenset()
