# app/core/rate_limit.py

import time
from collections import deque

from fastapi import HTTPException, Request

# In-memory, per-process sliding-window counters — fine at this app's
# single-container, single-instance scale (see README). A multi-replica
# deployment would need a shared store (e.g. Redis) instead, since each
# process would otherwise track its own independent counts and the
# effective limit would multiply by the replica count.
_hits: dict[str, deque[float]] = {}


def check_rate_limit(key: str, limit: int, window_seconds: float) -> None:
    """Raises HTTPException(429) if `key` has already made `limit` calls
    within the trailing `window_seconds`; otherwise records this call and
    returns normally.

    Empty buckets are dropped immediately after pruning rather than kept
    around forever, so the dict only grows with currently-active keys, not
    every distinct key ever seen.
    """
    now = time.monotonic()
    bucket = _hits.get(key)
    if bucket is not None:
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if not bucket:
            del _hits[key]
            bucket = None

    if bucket is not None and len(bucket) >= limit:
        retry_after = max(1, int(window_seconds - (now - bucket[0])))
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    _hits.setdefault(key, deque()).append(now)


def client_ip(request: Request) -> str:
    """Best-effort client IP: Railway terminates TLS at its edge and
    forwards the original client via X-Forwarded-For (same proxy pattern
    already used for scheme detection in app/routes/auth.py); falls back to
    the direct connecting peer for local dev, where there's no proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
