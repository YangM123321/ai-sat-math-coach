"""Unit tests for MemoryRateLimiter's bounded-storage behavior and the
PR6/PR14 instance-isolation guarantee (Phase 1.5 PR 14).

Kept in a separate file from tests/test_rate_limiter_service.py (PR6-era)
specifically so that file remains untouched -- see the approved
PR14_ARCHITECTURE_REVIEW.md, §17/§18.
"""

import threading

from app.services.rate_limiter_service import (
    MemoryRateLimiter,
    get_api_rate_limiter,
    get_rate_limiter,
)


class _FakeClock:
    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# --- Unbounded when max_keys=None (matches PR6's own instance exactly) ----


def test_unbounded_when_max_keys_is_none():
    clock = _FakeClock()
    limiter = MemoryRateLimiter(now=clock)
    for i in range(5000):
        limiter.check(f"key-{i}", max_attempts=10, window_seconds=60)
    assert len(limiter._state) == 5000


# --- Capacity is never exceeded --------------------------------------------


def test_capacity_is_never_exceeded():
    clock = _FakeClock()
    limiter = MemoryRateLimiter(now=clock, max_keys=10)
    for i in range(100):
        limiter.check(f"key-{i}", max_attempts=10, window_seconds=60)
        assert len(limiter._state) <= 10


# --- Stale entries are removed before LRU eviction is attempted -----------


def test_stale_entries_are_evicted_before_lru_eviction():
    clock = _FakeClock()
    limiter = MemoryRateLimiter(now=clock, max_keys=3)
    limiter.check("a", max_attempts=5, window_seconds=60)
    limiter.check("b", max_attempts=5, window_seconds=60)
    limiter.check("c", max_attempts=5, window_seconds=60)

    # Two full windows later, "a" and "b" are stale; refresh "c" so it
    # alone survives the sweep. Refreshing an *existing* key never
    # triggers capacity handling by itself (§11, point 6: only a *new*
    # key insertion does) -- the sweep runs on the next new-key insert.
    clock.advance(121)
    limiter.check("c", max_attempts=5, window_seconds=60)

    # A new key is admitted -- the stale sweep alone freed enough space,
    # without requiring the single-extra-LRU-eviction fallback at all.
    limiter.check("d", max_attempts=5, window_seconds=60)
    assert set(limiter._state.keys()) == {"c", "d"}


def test_stale_sweep_can_free_multiple_slots_at_once():
    clock = _FakeClock()
    limiter = MemoryRateLimiter(now=clock, max_keys=5)
    for key in ("a", "b", "c", "d", "e"):
        limiter.check(key, max_attempts=5, window_seconds=60)

    clock.advance(121)  # all five are now stale
    limiter.check("f", max_attempts=5, window_seconds=60)
    assert set(limiter._state.keys()) == {"f"}


# --- LRU eviction when nothing is stale ------------------------------------


def test_lru_eviction_when_no_stale_entries_exist():
    clock = _FakeClock()
    limiter = MemoryRateLimiter(now=clock, max_keys=3)
    limiter.check("a", max_attempts=5, window_seconds=60)
    limiter.check("b", max_attempts=5, window_seconds=60)
    limiter.check("c", max_attempts=5, window_seconds=60)

    # Touch "a" again -- "b" becomes the least-recently-attempted entry.
    limiter.check("a", max_attempts=5, window_seconds=60)
    limiter.check("d", max_attempts=5, window_seconds=60)  # triggers eviction

    assert "b" not in limiter._state
    assert set(limiter._state.keys()) == {"a", "c", "d"}


# --- Recency basis: every attempt, allowed or denied -- not allowed-only --


def test_recency_refreshes_on_denied_requests_not_only_allowed():
    clock = _FakeClock()
    limiter = MemoryRateLimiter(now=clock, max_keys=2)
    r1 = limiter.check("attacker", max_attempts=1, window_seconds=60)
    assert r1.allowed is True
    r2 = limiter.check("attacker", max_attempts=1, window_seconds=60)
    assert r2.allowed is False  # attacker is now being throttled

    limiter.check("victim", max_attempts=5, window_seconds=60)

    # Touch attacker again -- still denied -- this must still count as
    # "seen" and refresh its recency (the architecture's explicit,
    # attempt-based, not allowed-only, choice).
    r3 = limiter.check("attacker", max_attempts=1, window_seconds=60)
    assert r3.allowed is False

    limiter.check("newcomer", max_attempts=5, window_seconds=60)  # triggers eviction

    assert (
        "attacker" in limiter._state
    ), "an actively-hammering identity must not be evicted"
    assert (
        "victim" not in limiter._state
    ), "victim was idle since insertion and is the true LRU entry"
    assert "newcomer" in limiter._state


# --- New-identity admission after eviction ---------------------------------


def test_new_identity_is_always_admitted_after_eviction():
    clock = _FakeClock()
    limiter = MemoryRateLimiter(now=clock, max_keys=1)
    limiter.check("a", max_attempts=5, window_seconds=60)
    limiter.check("b", max_attempts=5, window_seconds=60)
    assert set(limiter._state.keys()) == {"b"}


# --- Capacity management never triggers the fail-open path ----------------


def test_capacity_eviction_result_is_not_the_fail_open_sentinel():
    """Eviction is normal housekeeping, not a failure -- the returned
    result for the request that triggered eviction must be the real,
    computed result, not the generic fail-open placeholder (which would
    always report `remaining == max_attempts`)."""
    clock = _FakeClock()
    limiter = MemoryRateLimiter(now=clock, max_keys=1)
    limiter.check("a", max_attempts=5, window_seconds=60)
    result = limiter.check(
        "b", max_attempts=5, window_seconds=60
    )  # evicts "a", admits "b"
    assert result.allowed is True
    assert (
        result.remaining == 4
    )  # proves real computation ran for this call, not fail-open


# --- Concurrency safety ------------------------------------------------------


def test_concurrent_distinct_keys_never_exceed_capacity():
    limiter = MemoryRateLimiter(max_keys=20)

    def hit(i: int) -> None:
        limiter.check(f"key-{i}", max_attempts=1000, window_seconds=60)

    threads = [threading.Thread(target=hit, args=(i,)) for i in range(200)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(limiter._state) <= 20


# --- get_rate_limiter() vs. get_api_rate_limiter() -------------------------


def test_get_rate_limiter_and_get_api_rate_limiter_are_distinct_instances():
    assert get_rate_limiter() is not get_api_rate_limiter()
    assert isinstance(get_rate_limiter(), MemoryRateLimiter)
    assert isinstance(get_api_rate_limiter(), MemoryRateLimiter)
    # Stable across repeated calls -- both are @lru_cache singletons.
    assert get_rate_limiter() is get_rate_limiter()
    assert get_api_rate_limiter() is get_api_rate_limiter()


def test_get_rate_limiter_and_get_api_rate_limiter_share_no_state():
    auth_limiter = get_rate_limiter()
    api_limiter = get_api_rate_limiter()
    auth_limiter.reset()
    api_limiter.reset()
    try:
        auth_limiter.check("probe", max_attempts=5, window_seconds=60)
        api_limiter.check("probe", max_attempts=5, window_seconds=60)
        assert auth_limiter._state is not api_limiter._state
        assert set(auth_limiter._state.keys()) == {"probe"}
        assert set(api_limiter._state.keys()) == {"probe"}

        # Isolated resets: clearing one must never clear the other.
        auth_limiter.reset()
        assert "probe" not in auth_limiter._state
        assert "probe" in api_limiter._state
    finally:
        auth_limiter.reset()
        api_limiter.reset()


def test_bounded_eviction_on_one_instance_never_touches_a_separate_instance():
    """Direct regression test for the PR6/PR14 capacity-isolation decision
    (architecture review §11): a synthetic flood driving one instance to
    its configured capacity must leave every key in a separate instance
    completely untouched -- proven with two directly constructed
    instances mirroring get_rate_limiter() (unbounded) and
    get_api_rate_limiter() (bounded)."""
    clock = _FakeClock()
    pr6_style = MemoryRateLimiter(now=clock)  # unbounded, like get_rate_limiter()
    pr14_style = MemoryRateLimiter(
        now=clock, max_keys=5
    )  # bounded, like get_api_rate_limiter()

    pr6_style.check("login_ip:1.2.3.4", max_attempts=10, window_seconds=300)
    for i in range(50):
        pr14_style.check(
            f"api_perimeter:flood-{i}", max_attempts=1000, window_seconds=60
        )

    assert len(pr14_style._state) <= 5
    assert list(pr6_style._state.keys()) == ["login_ip:1.2.3.4"]
