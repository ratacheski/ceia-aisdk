"""In-memory per-alias LLM pool and process-wide admission queue.

One ``LLM`` instance is reused per canonical alias. Generation is exclusive
per alias. A process-wide waiter cap of 8 makes overload visible as HTTP 429.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

DEFAULT_MAX_WAITERS = 8


class PoolOverflowError(Exception):
    """Raised when the process-wide waiter cap is already full."""


class ModelPool:
    """Reuse one ``LLM`` per alias and serialize generation on that instance.

    The waiter cap is optional so early stories can use the lock alone.
    """

    def __init__(
        self,
        *,
        factory: Callable[[str], Any] | None = None,
        max_waiters: int | None = DEFAULT_MAX_WAITERS,
    ) -> None:
        """Create an empty in-memory pool.

        Args:
            factory: Callable that constructs an ``LLM`` for an alias. Defaults
                to ``LLM(alias)`` imported lazily.
            max_waiters: Process-wide waiter cap. ``None`` disables the cap.
                The default is ``8``.
        """
        self._factory = factory
        self._instances: dict[str, Any] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._meta = asyncio.Lock()
        self._waiters = 0
        self.max_waiters = max_waiters

    @property
    def waiters(self) -> int:
        """Return the current number of requests waiting for an alias lock.

        Returns:
            Waiter count. In-flight holders are not included.
        """
        return self._waiters

    @asynccontextmanager
    async def hold(self, alias: str) -> AsyncIterator[Any]:
        """Acquire the per-alias lock and yield the pooled instance.

        Args:
            alias: Client model alias. Canonicalized on first construct.

        Yields:
            The pooled ``LLM`` (or test double) for ``alias``.

        Raises:
            PoolOverflowError: If the waiter cap is set and already full.
        """
        lock = await self._lock_for(alias)
        waiting = False
        if lock.locked():
            if self.max_waiters is not None and self._waiters >= self.max_waiters:
                raise PoolOverflowError("The generation queue is full.")
            self._waiters += 1
            waiting = True
        try:
            async with lock:
                if waiting:
                    self._waiters -= 1
                    waiting = False
                yield self._instance(alias)
        finally:
            if waiting:
                self._waiters -= 1

    async def _lock_for(self, alias: str) -> asyncio.Lock:
        """Return the exclusive lock for ``alias``.

        Args:
            alias: Client model alias.

        Returns:
            The per-alias asyncio lock.
        """
        async with self._meta:
            lock = self._locks.get(alias)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[alias] = lock
            return lock

    def _instance(self, alias: str) -> Any:
        """Return or construct the pooled instance for ``alias``.

        Args:
            alias: Client model alias.

        Returns:
            The cached instance.
        """
        instance = self._instances.get(alias)
        if instance is None:
            factory = self._factory or _default_factory
            instance = factory(alias)
            self._instances[alias] = instance
        return instance


def _default_factory(alias: str) -> Any:
    """Construct a library ``LLM`` for ``alias``.

    Args:
        alias: Cataloged alias from the client.

    Returns:
        A new ``LLM`` instance.
    """
    from ceia_aisdk.llm import LLM

    return LLM(alias)
