"""Unit tests for the sliding-window rate limiter. Expected values are hand-computed."""
from app.rate_limit import SlidingWindowLimiter


def test_allows_up_to_max_then_blocks():
    limiter = SlidingWindowLimiter(max_requests=3, window_seconds=60)
    assert limiter.allow("a", now=0) is True
    assert limiter.allow("a", now=1) is True
    assert limiter.allow("a", now=2) is True
    # 4th request within the window is the first to exceed max_requests=3.
    assert limiter.allow("a", now=3) is False


def test_window_slides_and_old_hits_expire():
    limiter = SlidingWindowLimiter(max_requests=2, window_seconds=10)
    assert limiter.allow("a", now=0) is True
    assert limiter.allow("a", now=1) is True
    assert limiter.allow("a", now=2) is False  # still within the 10s window of both hits
    # now=11 is past the window for the hit at t=0 (cutoff = 11-10 = 1, so t=0 expires)
    # but the hit at t=1 is still within [1, 11] and counts, so this is the 2nd live hit.
    assert limiter.allow("a", now=11) is True
    # A 3rd request at the same instant now has 2 live hits (t=1, t=11) -> blocked.
    assert limiter.allow("a", now=11) is False


def test_keys_are_independent():
    limiter = SlidingWindowLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("a", now=0) is True
    assert limiter.allow("b", now=0) is True
    assert limiter.allow("a", now=0) is False
    assert limiter.allow("b", now=0) is False


def test_reset_clears_state():
    limiter = SlidingWindowLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("a", now=0) is True
    assert limiter.allow("a", now=0) is False
    limiter.reset()
    assert limiter.allow("a", now=0) is True
