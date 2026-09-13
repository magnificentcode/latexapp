# app/core/concurrency.py

import asyncio
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class BusyError(Exception):
    """Raised when a slot didn't free up within the given wait timeout."""


async def run_bounded(semaphore: asyncio.Semaphore, wait_timeout: float, func: Callable[[], Awaitable[T]]) -> T:
    """Runs `func` once a slot on `semaphore` is available, waiting up to
    `wait_timeout` seconds for one to free up.

    A bounded wait (rather than either unlimited queueing or an instant
    reject) absorbs a short burst of contention gracefully while still
    failing fast — as BusyError — if the backlog doesn't clear in
    reasonable time. The slot is always released, including when `func`
    raises, so a failed call never leaks a permanently-held slot.
    """
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=wait_timeout)
    except asyncio.TimeoutError:
        raise BusyError()

    try:
        return await func()
    finally:
        semaphore.release()
