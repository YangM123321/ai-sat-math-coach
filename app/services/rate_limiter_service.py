"""Rate limiting for authentication endpoints (Phase 1.5 PR 6) and for
general `/api/v1/*` abuse protection (Phase 1.5 PR 14).

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
from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Protocol

from app.core.config import get_settings


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
    # Stored per-entry (Phase 1.5 PR 14) so a capacity-triggered eviction
    # sweep can determine staleness for *any* key, even though this one
    # shared instance holds entries created under different window_seconds
    # (PR14's five tiers). Not a "last access" field -- OrderedDict's own
    # ordering already tracks recency (see move_to_end below); this is only
    # the window size needed to re-derive "is this entry stale" for a key
    # other than the one the current check() call is for.
    window_seconds: int


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

    Bounded memory (Phase 1.5 PR 14, opt-in): passing `max_keys` caps the
    number of distinct keys this instance holds. PR6's own instance never
    passes it and remains exactly as it always has -- unbounded. When set,
    a *new* key that would push `len(self._state)` to `max_keys` triggers,
    inline under the existing lock: first a cheap sweep removing every
    stale entry (more than one full window old, same threshold `_check`
    already uses for its own reset logic), then -- only if that alone was
    insufficient -- exactly one additional eviction of the single
    least-recently-*attempted* entry (allowed or denied; `move_to_end` is
    called on every check(), not only allowed ones, so an actively-
    throttled identity is never made to look artificially stale just
    because it keeps getting denied). A new identity is always admitted
    after eviction -- capacity pressure never locks out a brand-new caller.
    This bookkeeping is normal housekeeping, not a failure: it never
    raises, so it can never trigger the fail-open path below.
    """

    def __init__(self, now: Callable[[], float] = time.time, max_keys: int | None = None):
        self._now = now
        self._lock = threading.Lock()
        self._state: OrderedDict[str, _Window] = OrderedDict()
        self._max_keys = max_keys

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
            if state is None:
                if self._max_keys is not None and len(self._state) >= self._max_keys:
                    self._evict_for_capacity_locked(now)
                state = _Window(bucket=bucket, current=0, previous=0, window_seconds=window_seconds)
            elif bucket - state.bucket > 1:
                state = _Window(bucket=bucket, current=0, previous=0, window_seconds=window_seconds)
            elif bucket != state.bucket:
                state = _Window(bucket=bucket, current=0, previous=state.current, window_seconds=window_seconds)
            state.current += 1
            self._state[key] = state
            self._state.move_to_end(key)
            current, previous = state.current, state.previous

        elapsed = now - bucket * window_seconds
        weight = max(0.0, 1 - (elapsed / window_seconds))
        estimated = previous * weight + current
        allowed = estimated <= max_attempts
        remaining = max(0, int(max_attempts - estimated))
        reset_seconds = max(1, int(window_seconds - elapsed))
        return RateLimitResult(allowed=allowed, limit=max_attempts, remaining=remaining, reset_seconds=reset_seconds)

    def _evict_for_capacity_locked(self, now: float) -> None:
        """Must be called with self._lock held, only when self._max_keys is
        set and a brand-new key is about to be inserted at capacity. Frees
        at least one slot: sweep every stale entry first (cheap), then --
        only if still at capacity -- evict exactly the one
        least-recently-attempted entry (the front of the OrderedDict, since
        move_to_end keeps the most recently attempted key at the back).

        Known characteristic, accepted for now: the stale sweep is O(n) in
        the current key count, and re-runs on every subsequent new key once
        already at capacity -- under a sustained flood of unique keys at
        capacity this adds per-request lock-held work. Bounded by
        `max_keys` (default 50,000) and cheap in absolute terms at that
        scale; revisit alongside the Redis migration (T2) if this ever
        becomes a real bottleneck."""
        stale_keys = [
            existing_key
            for existing_key, window in self._state.items()
            if int(now // window.window_seconds) - window.bucket > 1
        ]
        for existing_key in stale_keys:
            del self._state[existing_key]
        if self._state and len(self._state) >= self._max_keys:
            self._state.popitem(last=False)

    def reset(self) -> None:
        """Test-only: clear all counters."""
        with self._lock:
            self._state.clear()


@lru_cache
def get_rate_limiter() -> MemoryRateLimiter:
    return MemoryRateLimiter()


@lru_cache
def get_api_rate_limiter() -> MemoryRateLimiter:
    """A second, independent MemoryRateLimiter instance dedicated to
    general /api/v1/* rate limiting (Phase 1.5 PR 14) -- kept structurally
    separate from PR6's own get_rate_limiter() so that PR14 traffic can
    never evict or reset a PR6 authentication bucket (see
    docs/security/THREAT_MODEL.md, T11). Bounded via
    settings.rate_limit_max_stored_keys; PR6's instance remains unbounded."""
    return MemoryRateLimiter(max_keys=get_settings().rate_limit_max_stored_keys)
