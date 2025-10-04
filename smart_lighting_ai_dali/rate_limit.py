from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, Request, status

from .config import get_settings


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.requests: dict[str, Deque[float]] = defaultdict(deque)

    def check(self, request: Request) -> None:
        identifier = request.client.host if request.client else "unknown"
        window = self.settings.rate_limit_window_seconds
        limit = self.settings.rate_limit_requests
        now = time.time()
        queue = self.requests[identifier]
        while queue and now - queue[0] > window:
            queue.popleft()
        if len(queue) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
        queue.append(now)


def get_rate_limiter() -> InMemoryRateLimiter:
    return InMemoryRateLimiter()


__all__ = ["InMemoryRateLimiter", "get_rate_limiter"]
