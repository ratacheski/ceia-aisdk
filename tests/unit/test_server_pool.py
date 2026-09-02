"""Unit tests for the per-alias pool and waiter cap."""

from __future__ import annotations

import asyncio

import pytest

from ceia_aisdk.server.pool import DEFAULT_MAX_WAITERS, ModelPool, PoolOverflowError


def test_default_waiter_cap_is_eight() -> None:
    assert DEFAULT_MAX_WAITERS == 8
    pool = ModelPool(factory=lambda alias: object())
    assert pool.max_waiters == 8


def test_ninth_waiter_is_rejected_and_in_flight_is_not_a_waiter() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    pool = ModelPool(factory=lambda alias: object(), max_waiters=8)

    async def holder() -> None:
        async with pool.hold("llm/small"):
            started.set()
            await release.wait()

    async def waiter() -> None:
        async with pool.hold("llm/small"):
            return

    async def overflow() -> None:
        with pytest.raises(PoolOverflowError):
            async with pool.hold("llm/small"):
                return

    async def main() -> None:
        hold_task = asyncio.create_task(holder())
        await started.wait()
        assert pool.waiters == 0
        waiters = [asyncio.create_task(waiter()) for _ in range(8)]
        for _ in range(50):
            if pool.waiters == 8:
                break
            await asyncio.sleep(0.01)
        assert pool.waiters == 8
        await overflow()
        release.set()
        await hold_task
        await asyncio.gather(*waiters)
        assert pool.waiters == 0

    asyncio.run(main())
