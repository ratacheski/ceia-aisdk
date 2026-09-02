"""Multi-turn generation session bound to one LLM instance.

``Session`` is not thread-safe. Concurrent use from more than one thread is
undefined.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from ceia_aisdk.errors import AISDKError, GenerationError
from ceia_aisdk.llm.backend import _reraise_backend_error

if TYPE_CHECKING:
    from ceia_aisdk.llm.model import LLM

_OVERFLOW_REMEDIATION = (
    "Shorten the session history or raise [llm] context_length and construct a new LLM."
)


class Session:
    """Ordered chat history bound to one ``LLM`` instance.

    The session is not thread-safe. ``chat`` on the owner does not append to
    this history.
    """

    def __init__(self, owner: LLM, *, system: str | None = None) -> None:
        """Create a session owned by one generator.

        Args:
            owner: ``LLM`` instance that performs generation.
            system: Optional system prompt stored as the first message.
        """
        self._owner = owner
        self._messages: list[dict[str, str]] = []
        if system:
            self._messages.append({"role": "system", "content": system})

    def send(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> str:
        """Append a user turn, generate, and retain the assistant reply.

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
        self._messages.append({"role": "user", "content": prompt})
        try:
            text = self._generate(max_tokens=max_tokens, temperature=temperature, seed=seed)
        except Exception:
            self._messages.pop()
            raise
        self._messages.append({"role": "assistant", "content": text})
        return text

    def stream(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> Iterator[str]:
        """Append a user turn and yield assistant chunks while retaining history.

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
        self._messages.append({"role": "user", "content": prompt})
        chunks: list[str] = []
        try:
            for chunk in self._stream(max_tokens=max_tokens, temperature=temperature, seed=seed):
                chunks.append(chunk)
                yield chunk
        except Exception:
            self._messages.pop()
            raise
        self._messages.append({"role": "assistant", "content": "".join(chunks)})

    def _generate(self, *, max_tokens: int, temperature: float, seed: int | None) -> str:
        """Run a non-streaming completion against retained messages.

        Args:
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            seed: Optional generation seed.

        Returns:
            Assistant text.

        Raises:
            GenerationError: If generation fails.
            DeviceError: If the backend reports out-of-memory.
        """
        try:
            text = self._owner._backend.generate(
                self._messages,
                max_tokens=max_tokens,
                temperature=temperature,
                seed=seed,
            )
        except AISDKError:
            raise
        except Exception as exc:
            _reraise_backend_error(exc)
            raise
        if not isinstance(text, str) or not text.strip():
            raise GenerationError(
                "Local generation returned an empty completion.",
                remediation=_OVERFLOW_REMEDIATION,
            )
        return text

    def _stream(self, *, max_tokens: int, temperature: float, seed: int | None) -> Iterator[str]:
        """Yield chunks against retained messages.

        Args:
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            seed: Optional generation seed.

        Yields:
            Assistant chunks.

        Raises:
            GenerationError: If generation fails.
            DeviceError: If the backend reports out-of-memory.
        """
        try:
            yield from self._owner._backend.stream(
                self._messages,
                max_tokens=max_tokens,
                temperature=temperature,
                seed=seed,
            )
        except AISDKError:
            raise
        except Exception as exc:
            _reraise_backend_error(exc)
            raise
