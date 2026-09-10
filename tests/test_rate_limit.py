from collections import defaultdict, deque
import pytest
from backend import rate_limit
from backend.account_errors import AccountError


@pytest.fixture
def limiter(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(rate_limit, "_events", defaultdict(deque))
    monkeypatch.setattr(rate_limit, "_expires", {})
    monkeypatch.setattr(rate_limit, "_last_cleanup", 0.0)
    monkeypatch.setattr(rate_limit, "MAX_KEYS", 2)
    monkeypatch.setattr(rate_limit, "monotonic", lambda: clock[0])
    return clock


def test_capacity_never_evicts_active_keys(limiter):
    rate_limit.enforce("a", 1, 30)
    rate_limit.enforce("b", 1, 30)
    with pytest.raises(AccountError):
        rate_limit.enforce("c", 1, 30)
    assert set(rate_limit._events) == {"a", "b"}
    with pytest.raises(AccountError):
        rate_limit.enforce("a", 1, 30)


def test_expired_capacity_is_reclaimed(limiter):
    rate_limit.enforce("a", 1, 30)
    rate_limit.enforce("b", 1, 30)
    limiter[0] = 130.0
    rate_limit.enforce("c", 1, 30)
    assert set(rate_limit._events) == {"c"}
    assert set(rate_limit._expires) == {"c"}


def test_clear_releases_event_and_expiry(limiter):
    rate_limit.enforce("a", 1, 30)
    rate_limit.clear("a")
    assert "a" not in rate_limit._events
    assert "a" not in rate_limit._expires
    rate_limit.enforce("a", 1, 30)
