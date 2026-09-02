"""Asynchronous local LLM mirror that offloads blocking generation.

``AsyncLLM`` is not thread-safe. The llama.cpp binding is blocking, so chat
and stream run in a worker thread via ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

from ceia_aisdk.config import AISDKConfig
from ceia_aisdk.llm.model import LLM
from ceia_aisdk.llm.tools import ToolDeclaration

_SENTINEL = object()


class AsyncLLM:
    """Async mirror of ``LLM`` with the same constructor and error types.

    Instances are not thread-safe. Generation uses ``asyncio.to_thread`` because
    the local inference binding is blocking.
    """

    def __init__(
        self,
        alias: str | None = None,
        *,
        config: AISDKConfig | None = None,
        device: str | None = None,
        context_length: int | None = None,
        tools: Sequence[ToolDeclaration] | None = None,
    ) -> None:
        """Construct an async generator that wraps a synchronous ``LLM``.

        The instance is not thread-safe. Construction may obtain cache files
        and load the blocking backend in the calling thread.

        Args:
            alias: Cataloged alias or unqualified size.
            config: Effective SDK configuration.
            device: Per-instance device override.
            context_length: Per-instance context window override.
            tools: Optional tool declarations.

        Raises:
            ConfigError: If settings or core configuration are invalid.
            ModelNotFoundError: If the alias is not in the active catalog.
            DownloadError: If the artifact cannot be obtained.
            DeviceError: If an explicit CUDA device cannot be used.
            CapabilityError: If tools are passed to an alias without ``tool_use``.
            GenerationError: If the local runtime cannot load the file.
        """
        self._sync = LLM(
            alias,
            config=config,
            device=device,
            context_length=context_length,
            tools=tools,
        )

    @property
    def alias(self) -> str:
        """Return the canonical catalog alias.

        Returns:
            Canonical ``domain/size@N`` string.
        """
        return self._sync.alias

    @property
    def device(self) -> str:
        """Return the effective generation device.

        Returns:
            ``cpu`` or ``cuda:N``.
        """
        return self._sync.device

    async def chat(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> str:
        """Await a one-shot completion without blocking the event loop.

        The llama.cpp binding is blocking; this method offloads it with
        ``asyncio.to_thread``.

        Args:
            prompt: User prompt text.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            seed: Optional generation seed.

        Returns:
            Assistant text.

        Raises:
            GenerationError: If generation fails for a non-device reason.
            DeviceError: If the backend reports out-of-memory.
        """
        return await asyncio.to_thread(
            self._sync.chat,
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            seed=seed,
        )

    async def stream(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> AsyncIterator[str]:
        """Yield completion chunks without blocking the event loop beyond the binding.

        Args:
            prompt: User prompt text.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            seed: Optional generation seed.

        Yields:
            String chunks from the synchronous stream, pulled via
            ``asyncio.to_thread``.

        Raises:
            GenerationError: If generation fails for a non-device reason.
            DeviceError: If the backend reports out-of-memory.
        """
        iterator = self._sync.stream(
            prompt, max_tokens=max_tokens, temperature=temperature, seed=seed
        )

        def _next() -> object:
            return next(iterator, _SENTINEL)

        while True:
            chunk = await asyncio.to_thread(_next)
            if chunk is _SENTINEL:
                break
            assert isinstance(chunk, str)
            yield chunk

    def session(self, system: str | None = None) -> AsyncSession:
        """Return an async session bound to this instance.

        Args:
            system: Optional system prompt retained for the session.

        Returns:
            An ``AsyncSession`` that is not thread-safe.
        """
        return AsyncSession(self, system=system)


class AsyncSession:
    """Async multi-turn session bound to one ``AsyncLLM``.

    The session is not thread-safe. Generation is offloaded with
    ``asyncio.to_thread``.
    """

    def __init__(self, owner: AsyncLLM, *, system: str | None = None) -> None:
        """Create an async session.

        Args:
            owner: ``AsyncLLM`` instance that performs generation.
            system: Optional system prompt stored as the first message.
        """
        self._sync_session = owner._sync.session(system=system)

    async def send(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> str:
        """Append a user turn and await the assistant reply.

        Args:
            prompt: User prompt text.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            seed: Optional generation seed.

        Returns:
            Assistant text for this turn.

        Raises:
            GenerationError: If generation fails, including context overflow.
            DeviceError: If the backend reports out-of-memory.
        """
        return await asyncio.to_thread(
            self._sync_session.send,
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            seed=seed,
        )

    async def stream(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> AsyncIterator[str]:
        """Append a user turn and yield assistant chunks.

        Args:
            prompt: User prompt text.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            seed: Optional generation seed.

        Yields:
            Assistant text chunks for this turn.

        Raises:
            GenerationError: If generation fails, including context overflow.
            DeviceError: If the backend reports out-of-memory.
        """
        iterator = self._sync_session.stream(
            prompt, max_tokens=max_tokens, temperature=temperature, seed=seed
        )

        def _next() -> object:
            return next(iterator, _SENTINEL)

        while True:
            chunk = await asyncio.to_thread(_next)
            if chunk is _SENTINEL:
                break
            assert isinstance(chunk, str)
            yield chunk
