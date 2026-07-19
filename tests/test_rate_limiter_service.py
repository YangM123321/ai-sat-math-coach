"""Unit tests for MemoryRateLimiter (Phase 1.5 PR 6)."""
import threading

from app.services.rate_limiter_service import MemoryRateLimiter


class _FakeClock:
    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_allows_calls_under_the_limit():
    clock = _FakeClock()
    limiter = MemoryRateLimiter(now=clock)
    for _ in range(5):
        result = limiter.check("k", max_attempts=5, window_seconds=60)
        assert result.allowed is True
    assert result.remaining == 0


def test_denies_calls_over_the_limit():
    clock = _FakeClock()
    limiter = MemoryRateLimiter(now=clock)
    for _ in range(5):
        limiter.check("k", max_attempts=5, window_seconds=60)
    result = limiter.check("k", max_attempts=5, window_seconds=60)
    assert result.allowed is False
    assert result.remaining == 0
    assert result.limit == 5
    assert 1 <= result.reset_seconds <= 60


def test_independent_keys_do_not_interfere():
    clock = _FakeClock()
    limiter = MemoryRateLimiter(now=clock)
    for _ in range(5):
        limiter.check("a", max_attempts=5, window_seconds=60)
    result_a = limiter.check("a", max_attempts=5, window_seconds=60)
    result_b = limiter.check("b", max_attempts=5, window_seconds=60)
    assert result_a.allowed is False
    assert result_b.allowed is True


def test_full_window_elapse_restores_access():
    clock = _FakeClock()
    limiter = MemoryRateLimiter(now=clock)
    for _ in range(5):
        limiter.check("k", max_attempts=5, window_seconds=60)
    assert limiter.check("k", max_attempts=5, window_seconds=60).allowed is False

    # Two full windows later, both the current and blended-previous
    # window counters have rolled past -- access is restored.
    clock.advance(121)
    result = limiter.check("k", max_attempts=5, window_seconds=60)
    assert result.allowed is True


def test_sliding_window_blends_previous_window_near_the_boundary():
    """A caller that used up the limit right before a window boundary
    should still be throttled just after it rolls -- a plain fixed-window
    counter would incorrectly allow a fresh burst here."""
    clock = _FakeClock()
    limiter = MemoryRateLimiter(now=clock)
    for _ in range(5):
        limiter.check("k", max_attempts=5, window_seconds=60)

    # Cross into the next window, but only barely.
    clock.advance(61)
    result = limiter.check("k", max_attempts=5, window_seconds=60)
    assert result.allowed is False


def test_reset_clears_all_state():
    clock = _FakeClock()
    limiter = MemoryRateLimiter(now=clock)
    for _ in range(5):
        limiter.check("k", max_attempts=5, window_seconds=60)
    assert limiter.check("k", max_attempts=5, window_seconds=60).allowed is False

    limiter.reset()
    assert limiter.check("k", max_attempts=5, window_seconds=60).allowed is True


def test_fails_open_when_backend_raises(monkeypatch):
    limiter = MemoryRateLimiter()
    monkeypatch.setattr(limiter, "_check", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    result = limiter.check("k", max_attempts=5, window_seconds=60)
    assert result.allowed is True


def test_concurrent_increments_are_not_lost():
    clock = _FakeClock()
    limiter = MemoryRateLimiter(now=clock)
    results = []
    lock = threading.Lock()

    def hit():
        r = limiter.check("k", max_attempts=1000, window_seconds=60)
        with lock:
            results.append(r)

    threads = [threading.Thread(target=hit) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    remaining_values = {r.remaining for r in results}
    assert len(remaining_values) == 50
