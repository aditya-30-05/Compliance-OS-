"""
In-memory rate limiter using sliding window.
Production alternative: use Redis-backed rate limiter.
"""

import time
from collections import defaultdict
from fastapi import HTTPException, Request, status


class RateLimiter:
    """Simple in-memory sliding window rate limiter."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_key(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
        return ip

    def check(self, request: Request) -> None:
        key = self._get_key(request)
        now = time.time()
        cutoff = now - self.window_seconds

        # Prune old entries
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

        if len(self._requests[key]) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds}s.",
            )

        self._requests[key].append(now)


# Pre-configured limiters
general_limiter = RateLimiter(max_requests=60, window_seconds=60)
ai_limiter = RateLimiter(max_requests=20, window_seconds=60)
auth_limiter = RateLimiter(max_requests=10, window_seconds=60)
