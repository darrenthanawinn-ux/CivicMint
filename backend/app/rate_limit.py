"""
In-process sliding-window rate limiter.

For a hackathon MVP this avoids the operational overhead of standing up
Redis, while still implementing a real sliding-window algorithm (not the
weaker fixed-window-bucket approach) so behavior is representative of what
you'd deploy against Redis (via a sorted set) in production. The
`SlidingWindowLimiter` class is intentionally storage-agnostic in interface
so swapping the in-memory dict for Redis later is a one-file change.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict

from fastapi import HTTPException, Request, status

from app.config import get_settings


class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Returns (allowed, remaining)."""
        now = time.monotonic()
        window_start = now - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < window_start:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False, 0
            hits.append(now)
            return True, self.max_requests - len(hits)

    def retry_after(self, key: str) -> int:
        with self._lock:
            hits = self._hits[key]
            if not hits:
                return 0
            elapsed = time.monotonic() - hits[0]
            return max(0, int(self.window_seconds - elapsed) + 1)


_settings = get_settings()
permit_analysis_limiter = SlidingWindowLimiter(
    max_requests=_settings.RATE_LIMIT_MAX_REQUESTS,
    window_seconds=_settings.RATE_LIMIT_WINDOW_SECONDS,
)


def _client_key(request: Request) -> str:
    # Prefer a forwarded header (behind a reverse proxy in real deployments),
    # fall back to the direct peer address. Never trust this alone for auth,
    # but it's sufficient as an abuse-throttling key for a demo/MVP.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request) -> None:
    """FastAPI dependency: raises 429 with Retry-After if the caller is over budget."""
    key = _client_key(request)
    allowed, remaining = permit_analysis_limiter.check(key)
    if not allowed:
        retry_after = permit_analysis_limiter.retry_after(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please slow down and try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )
