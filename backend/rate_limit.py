"""Small process-local rate limiter for the local deployment.

It is intentionally dependency-free. For multiple production workers, put a
reverse-proxy or shared rate limiter in front of the API.
"""
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Deque, Dict, Tuple

from fastapi import status

from .account_errors import AccountError


_events: Dict[str, Deque[float]] = defaultdict(deque)
_lock = Lock()
_expires: Dict[str, float] = {}
MAX_KEYS = 10000
_last_cleanup = 0.0


def enforce(key: str, limit: int, window_seconds: int) -> None:
    global _last_cleanup
    now = monotonic()
    cutoff = now - window_seconds
    with _lock:
        if now - _last_cleanup >= 60 or len(_events) >= MAX_KEYS:
            for expired_key in list(_events):
                if _expires.get(expired_key, 0) <= now:
                    _events.pop(expired_key, None)
                    _expires.pop(expired_key, None)
            _last_cleanup = now
        if key not in _events and len(_events) >= MAX_KEYS:
            raise AccountError("ACCOUNT_RATE_LIMITED", status_code=429, headers={"Retry-After": "60"})
        events = _events[key]
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= limit:
            retry_after = max(1, int(events[0] + window_seconds - now))
            raise AccountError(
                "ACCOUNT_RATE_LIMITED",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after)},
            )
        events.append(now)
        _expires[key] = now + window_seconds


def clear(key: str) -> None:
    with _lock:
        _events.pop(key, None)
        _expires.pop(key, None)
