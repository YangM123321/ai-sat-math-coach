"""Rate limiting for authentication endpoints (Phase 1.5 PR 6).

`RateLimiter` is a narrow interface (`check`) so the backend can be
swapped without touching the dependency/route layer above it --
`MemoryRateLimiter` here now, a future `RedisRateLimiter` once this app
is horizontally scaled (see docs/security/THREAT_MODEL.md, T2).

Algorithm: sliding-window counter (a weighted blend of the current and
previous fixed window), not a fixed-window counter (which allows a ~2x
burst right at a window boundary) and not a sliding-window log (exact,
but O(attempts) memory per key -- unnecessary precision for throttling
login attempts).
"""
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Protocol


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int  # seconds until the current window rolls over -- same units as Retry-After, not a Unix timestamp


class RateLimiter(Protocol):
    def check(self, key: str, *, max_attempts: int, window_seconds: int) -> RateLimitResult: ...


@dataclass
class _Window:
    bucket: int
    current: int
    previous: int


class MemoryRateLimiter:
    """In-process sliding-window limiter, keyed by an arbitrary string
    (e.g. "login_ip:1.2.3.4" or "login_account:student@example.com").

    Fail-open by explicit architecture-review decision: `check` never
    raises -- a bug in this in-memory implementation must not be able to
    lock every caller out of authentication. **This default should be
    re-evaluated once a Redis backend is introduced**: a network-backed
    limiter has real failure modes an in-process dict does not (connection
    errors, timeouts), and a production deployment may then prefer to fail
    closed instead. See docs/security/THREAT_MODEL.md (T2).

    Per-process only: state is not shared across multiple app instances/
    workers. Acceptable for this project's current single-instance
    deployment (docker-compose.yml runs one `api` service); revisit before
    horizontally scaling (see T2 residual risks).
    """

    def __init__(self, now: Callable[[], float] = time.time):
        self._now = now
        self._lock = threading.Lock()
        self._state: dict[str, _Window] = {}

    def check(self, key: str, *, max_attempts: int, window_seconds: int) -> RateLimitResult:
        try:
            return self._check(key, max_attempts=max_attempts, window_seconds=window_seconds)
        except Exception:
            # Fail-open: never let a bug here block authentication. See
            # class docstring.
            return RateLimitResult(allowed=True, limit=max_attempts, remaining=max_attempts, reset_seconds=window_seconds)

    def _check(self, key: str, *, max_attempts: int, window_seconds: int) -> RateLimitResult:
        now = self._now()
        bucket = int(now // window_seconds)
        with self._lock:
            state = self._state.get(key)
            if state is None or bucket - state.bucket > 1:
                state = _Window(bucket=bucket, current=0, previous=0)
            elif bucket != state.bucket:
                state = _Window(bucket=bucket, current=0, previous=state.current)
            state.current += 1
            self._state[key] = state
            current, previous = state.current, state.previous

        elapsed = now - bucket * window_seconds
        weight = max(0.0, 1 - (elapsed / window_seconds))
        estimated = previous * weight + current
        allowed = estimated <= max_attempts
        remaining = max(0, int(max_attempts - estimated))
        reset_seconds = max(1, int(window_seconds - elapsed))
        return RateLimitResult(allowed=allowed, limit=max_attempts, remaining=remaining, reset_seconds=reset_seconds)

    def reset(self) -> None:
        """Test-only: clear all counters."""
        with self._lock:
            self._state.clear()


@lru_cache
def get_rate_limiter() -> MemoryRateLimiter:
    return MemoryRateLimiter()
