"""In-memory sliding-window rate limiter for auth endpoints.

Single-process, single-instance only: state lives in a plain dict and resets
on restart or across workers. That's an accepted tradeoff for a self-hosted
app with one backend process (see docs/DECISIONS.md) — a multi-instance
deployment would need a shared store (e.g. Redis) instead.
"""
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        """Record and permit a request under `key`, or reject if over the limit."""
        now = time.monotonic() if now is None else now
        hits = self._hits[key]
        cutoff = now - self.window_seconds
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()


# 5 attempts/minute/IP for login (brute-force guard), 5/hour/IP for register
# (signup-spam guard). Both keyed by client IP — simple, per the task's own
# "simple in-memory sliding window is fine" — with the known limitation that
# clients behind a shared NAT/proxy share a bucket.
login_limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60)
register_limiter = SlidingWindowLimiter(max_requests=5, window_seconds=3600)
