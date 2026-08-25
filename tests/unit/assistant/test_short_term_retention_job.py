import asyncio
from typing import cast

from pytest import MonkeyPatch

from app.core.database.database import SessionFactory
from app.modules.assistant.infrastructure.conversation_memory.short_term.short_term_retention_job import (
    ShortTermRetentionJob,
)


def make_job(*, purge_interval_seconds: float = 3_600.0) -> ShortTermRetentionJob:
    return ShortTermRetentionJob(
        session_factory=cast(SessionFactory, object()),
        retention_days=90,
        assistant_conversation_retention_days=180,
        purge_interval_seconds=purge_interval_seconds,
    )


async def test_start_runs_purge_immediately(
    monkeypatch: MonkeyPatch,
) -> None:
    purge_called = asyncio.Event()
    calls = 0

    async def fake_purge(
        self: ShortTermRetentionJob,
    ) -> int:
        del self
        nonlocal calls
        calls += 1
        purge_called.set()
        return 0

    monkeypatch.setattr(
        ShortTermRetentionJob,
        "purge_expired",
        fake_purge,
    )

    job = make_job()

    await job.start()
    await asyncio.wait_for(purge_called.wait(), timeout=1.0)
    await job.stop()

    assert calls == 1


async def test_start_is_idempotent(
    monkeypatch: MonkeyPatch,
) -> None:
    purge_called = asyncio.Event()
    release_purge = asyncio.Event()
    calls = 0

    async def fake_purge(
        self: ShortTermRetentionJob,
    ) -> int:
        del self
        nonlocal calls
        calls += 1
        purge_called.set()
        await release_purge.wait()
        return 0

    monkeypatch.setattr(
        ShortTermRetentionJob,
        "purge_expired",
        fake_purge,
    )

    job = make_job()

    await job.start()
    await job.start()

    await asyncio.wait_for(purge_called.wait(), timeout=1.0)
    assert calls == 1

    release_purge.set()
    await job.stop()


async def test_stop_interrupts_interval_wait(
    monkeypatch: MonkeyPatch,
) -> None:
    purge_called = asyncio.Event()

    async def fake_purge(
        self: ShortTermRetentionJob,
    ) -> int:
        del self
        purge_called.set()
        return 0

    monkeypatch.setattr(
        ShortTermRetentionJob,
        "purge_expired",
        fake_purge,
    )

    job = make_job(purge_interval_seconds=3_600.0)

    await job.start()
    await asyncio.wait_for(purge_called.wait(), timeout=1.0)

    # This proves shutdown does not wait for the one-hour interval.
    await asyncio.wait_for(job.stop(), timeout=1.0)


async def test_temporary_failure_does_not_terminate_worker(
    monkeypatch: MonkeyPatch,
) -> None:
    second_attempt_completed = asyncio.Event()
    calls = 0

    async def fake_purge(
        self: ShortTermRetentionJob,
    ) -> int:
        del self
        nonlocal calls
        calls += 1

        if calls == 1:
            raise RuntimeError("temporary database failure")

        second_attempt_completed.set()
        return 0

    monkeypatch.setattr(
        ShortTermRetentionJob,
        "purge_expired",
        fake_purge,
    )

    job = make_job(purge_interval_seconds=0.01)

    await job.start()
    await asyncio.wait_for(
        second_attempt_completed.wait(),
        timeout=1.0,
    )
    await job.stop()

    assert calls >= 2
