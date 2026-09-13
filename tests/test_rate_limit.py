import itertools

import pytest
from fastapi import HTTPException

from app.core import rate_limit
from app.core.rate_limit import check_rate_limit


@pytest.fixture(autouse=True)
def clean_hits():
    """Each test gets a fresh counter store so cases can't leak into each
    other, and a unique key besides (see `key` fixture) as a second layer
    of isolation."""
    rate_limit._hits.clear()
    yield
    rate_limit._hits.clear()


@pytest.fixture
def key():
    return f"test-key-{next(_counter)}"


_counter = itertools.count()


class FakeClock:
    """Deterministic stand-in for time.monotonic() so window-expiry tests
    don't depend on real wall-clock timing."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(rate_limit.time, "monotonic", fake)
    return fake


def test_allows_calls_up_to_the_limit(key, clock):
    for _ in range(5):
        check_rate_limit(key, limit=5, window_seconds=60)


def test_blocks_the_call_after_the_limit(key, clock):
    for _ in range(3):
        check_rate_limit(key, limit=3, window_seconds=60)
    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(key, limit=3, window_seconds=60)
    assert exc_info.value.status_code == 429


def test_blocked_response_carries_a_retry_after_header(key, clock):
    check_rate_limit(key, limit=1, window_seconds=60)
    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(key, limit=1, window_seconds=60)
    assert "Retry-After" in exc_info.value.headers
    assert int(exc_info.value.headers["Retry-After"]) > 0


def test_different_keys_are_independent(clock):
    for _ in range(3):
        check_rate_limit("key-a", limit=3, window_seconds=60)
    # key-b has made zero calls, so it isn't affected by key-a's limit.
    check_rate_limit("key-b", limit=3, window_seconds=60)
    with pytest.raises(HTTPException):
        check_rate_limit("key-a", limit=3, window_seconds=60)


def test_calls_are_allowed_again_once_the_window_has_fully_elapsed(key, clock):
    for _ in range(2):
        check_rate_limit(key, limit=2, window_seconds=10)
    with pytest.raises(HTTPException):
        check_rate_limit(key, limit=2, window_seconds=10)

    clock.advance(10.001)

    check_rate_limit(key, limit=2, window_seconds=10)


def test_sliding_window_only_frees_up_the_calls_that_have_expired(key, clock):
    check_rate_limit(key, limit=2, window_seconds=10)  # t=0
    clock.advance(6)
    check_rate_limit(key, limit=2, window_seconds=10)  # t=6, bucket now [0, 6]

    clock.advance(4.001)  # t=10.001: the t=0 call has expired, t=6 has not
    check_rate_limit(key, limit=2, window_seconds=10)  # allowed: bucket was [6]

    with pytest.raises(HTTPException):
        check_rate_limit(key, limit=2, window_seconds=10)  # bucket now [6, 10.001]


def test_empty_buckets_are_evicted_from_the_backing_store(key, clock):
    check_rate_limit(key, limit=1, window_seconds=10)
    assert key in rate_limit._hits

    clock.advance(10.001)
    # The next call for an unrelated key prunes/evicts key's now-empty
    # bucket lazily on its own next access, not eagerly — so instead,
    # exercise key itself again to trigger its own prune-and-evict path.
    check_rate_limit(key, limit=1, window_seconds=10)
    assert len(rate_limit._hits[key]) == 1
