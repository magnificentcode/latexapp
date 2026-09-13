import asyncio

import pytest

from app.core.concurrency import BusyError, run_bounded


def test_a_single_call_runs_and_returns_its_result():
    async def scenario():
        sem = asyncio.Semaphore(1)
        return await run_bounded(sem, wait_timeout=1, func=lambda: _immediate("ok"))

    assert asyncio.run(scenario()) == "ok"


def test_slot_is_released_after_success_so_a_later_call_can_acquire_it():
    async def scenario():
        sem = asyncio.Semaphore(1)
        await run_bounded(sem, wait_timeout=1, func=lambda: _immediate("first"))
        # If the first call hadn't released the slot, this would time out.
        return await run_bounded(sem, wait_timeout=1, func=lambda: _immediate("second"))

    assert asyncio.run(scenario()) == "second"


def test_slot_is_released_even_when_func_raises():
    async def scenario():
        sem = asyncio.Semaphore(1)
        with pytest.raises(ValueError):
            await run_bounded(sem, wait_timeout=1, func=_raise_value_error)
        # A failed call must not leak a permanently-held slot.
        return await run_bounded(sem, wait_timeout=1, func=lambda: _immediate("recovered"))

    assert asyncio.run(scenario()) == "recovered"


def test_a_second_caller_waits_for_a_slot_held_by_a_slow_first_caller():
    async def scenario():
        sem = asyncio.Semaphore(1)
        events = []

        async def slow_work():
            events.append(("slow", "start"))
            await asyncio.sleep(0.1)
            events.append(("slow", "end"))
            return "slow"

        async def fast_work():
            events.append(("fast", "start"))
            events.append(("fast", "end"))
            return "fast"

        async def fast_caller():
            await asyncio.sleep(0.02)  # let slow_caller acquire the only slot first
            return await run_bounded(sem, wait_timeout=1, func=fast_work)

        await asyncio.gather(
            run_bounded(sem, wait_timeout=1, func=slow_work),
            fast_caller(),
        )
        return events

    events = asyncio.run(scenario())
    # With only one slot, fast_work must not run until slow_work has
    # finished and released it — the semaphore serializes them even
    # though fast_caller() itself started waiting earlier.
    assert events == [("slow", "start"), ("slow", "end"), ("fast", "start"), ("fast", "end")]


def test_raises_busy_error_if_no_slot_frees_up_within_the_wait_timeout():
    async def scenario():
        sem = asyncio.Semaphore(1)

        async def hold_forever():
            await asyncio.sleep(1)
            return "never gets here in this test"

        holder = asyncio.create_task(run_bounded(sem, wait_timeout=1, func=hold_forever))
        await asyncio.sleep(0.02)  # let `holder` acquire the only slot first

        with pytest.raises(BusyError):
            await run_bounded(sem, wait_timeout=0.05, func=lambda: _immediate("blocked"))

        holder.cancel()

    asyncio.run(scenario())


def test_multiple_slots_allow_that_many_concurrent_callers():
    async def scenario():
        sem = asyncio.Semaphore(2)
        concurrent = 0
        peak = 0

        async def track():
            nonlocal concurrent, peak
            concurrent += 1
            peak = max(peak, concurrent)
            await asyncio.sleep(0.05)
            concurrent -= 1
            return "done"

        await asyncio.gather(*(run_bounded(sem, wait_timeout=1, func=track) for _ in range(2)))
        return peak

    assert asyncio.run(scenario()) == 2


async def _immediate(value):
    return value


async def _raise_value_error():
    raise ValueError("boom")
