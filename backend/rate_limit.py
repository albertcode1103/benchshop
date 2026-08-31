"""Small process-local rate limiter for the local deployment.

It is intentionally dependency-free. For multiple production workers, put a
reverse-proxy or shared rate limiter in front of the API.
"""
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Deque, Dict, Tuple

from fastapi import HTTPException, status


_events: Dict[str, Deque[float]] = defaultdict(deque)
_lock = Lock()


def enforce(key: str, limit: int, window_seconds: int) -> None:
    now = monotonic()
    cutoff = now - window_seconds
    with _lock:
        events = _events[key]
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= limit:
            retry_after = max(1, int(events[0] + window_seconds - now))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试",
                headers={"Retry-After": str(retry_after)},
            )
        events.append(now)


def clear(key: str) -> None:
    with _lock:
        _events.pop(key, None)
