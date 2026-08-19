from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from math import ceil
from typing import Protocol

from app.modules.assistant.tool_gateway.domain import ToolRateLimit

ANONYMOUS_ACTOR = "__anonymous__"


@dataclass(frozen=True, slots=True)
class RateLimitVerdict:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class RateLimiterPort(Protocol):
    def try_consume(
        self,
        *,
        actor: str | None,
        tool_name: str,
        rate_limit: ToolRateLimit,
    ) -> RateLimitVerdict: ...


@dataclass(slots=True)
class _WindowCounter:
    window_start: float
    used: int


class FixedWindowRateLimiter:
    """Per-actor, per-tool fixed-window counter; the clock is injectable so limits stay deterministic."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock: Callable[[], float] = clock if clock is not None else time.monotonic
        self._counters: dict[tuple[str, str], _WindowCounter] = {}

    def try_consume(
        self,
        *,
        actor: str | None,
        tool_name: str,
        rate_limit: ToolRateLimit,
    ) -> RateLimitVerdict:
        key = (actor if actor is not None else ANONYMOUS_ACTOR, tool_name)
        now = self._clock()
        counter = self._counters.get(key)

        if counter is None or now - counter.window_start >= rate_limit.window_seconds:
            counter = _WindowCounter(window_start=now, used=0)
            self._counters[key] = counter

        if counter.used >= rate_limit.max_calls:
            elapsed = now - counter.window_start
            retry_after = max(1, ceil(rate_limit.window_seconds - elapsed))
            return RateLimitVerdict(
                allowed=False,
                remaining=0,
                retry_after_seconds=retry_after,
            )

        counter.used += 1
        return RateLimitVerdict(
            allowed=True,
            remaining=rate_limit.max_calls - counter.used,
            retry_after_seconds=0,
        )
