"""Private lazy llama.cpp adapter for local GGUF generation.

This module must not import ``llama_cpp`` at module level. The binding is
imported inside the factory that constructs a backend after ``ensure_local``.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, Protocol

from ceia_aisdk.errors import DeviceError, GenerationError

_OOM_REMEDIATION = 'Use a smaller alias such as llm/small, or set device="cpu" and retry.'
_GENERATION_REMEDIATION = (
    "Shorten the prompt or session history, raise [llm] context_length, or retry."
)


class InferenceBackend(Protocol):
    """Private generation backend bound to one local GGUF file."""

    def generate(
        self,
        messages: Sequence[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
        seed: int | None,
    ) -> str:
        """Return one completion string.

        Args:
            messages: Chat messages in role/content form.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            seed: Optional generation seed.

        Returns:
            The assistant text.
        """
        ...

    def stream(
        self,
        messages: Sequence[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
        seed: int | None,
    ) -> Iterator[str]:
        """Yield completion chunks.

        Args:
            messages: Chat messages in role/content form.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            seed: Optional generation seed.

        Returns:
            An iterator of string chunks from the backend.
        """
        ...


def create_backend(path: Path, *, n_ctx: int, n_gpu_layers: int) -> InferenceBackend:
    """Construct the llama.cpp backend after a local file is available.

    Args:
        path: Local GGUF path returned by ``ensure_local``.
        n_ctx: Effective context window.
        n_gpu_layers: ``0`` on CPU or ``-1`` on CUDA.

    Returns:
        A private inference backend.

    Raises:
        GenerationError: If the binding cannot be imported or the model cannot
            be loaded.
        DeviceError: If the binding reports an out-of-memory failure.
    """
    llama_cpp = _import_llama_cpp()
    try:
        model = llama_cpp.Llama(
            model_path=str(path),
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            verbose=False,
        )
    except Exception as exc:
        _reraise_backend_error(exc)
        raise
    return LlamaCppBackend(model)


def _import_llama_cpp() -> Any:
    """Import llama.cpp only when a backend is constructed.

    Returns:
        The imported ``llama_cpp`` module.

    Raises:
        GenerationError: If the optional runtime cannot be imported.
    """
    try:
        import llama_cpp
    except ImportError as exc:
        raise GenerationError(
            "The local inference runtime could not be imported.",
            remediation="Reinstall ceia-aisdk so llama-cpp-python is available.",
        ) from exc
    return llama_cpp


class LlamaCppBackend:
    """llama.cpp adapter that wraps native failures in public SDK errors."""

    def __init__(self, model: object) -> None:
        """Store the loaded llama.cpp handle.

        Args:
            model: Instantiated ``llama_cpp.Llama`` object.
        """
        self._model = model

    def generate(
        self,
        messages: Sequence[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
        seed: int | None,
    ) -> str:
        """Return one completion string.

        Args:
            messages: Chat messages in role/content form.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            seed: Optional generation seed.

        Returns:
            The assistant text.

        Raises:
            GenerationError: If generation fails for a non-device reason.
            DeviceError: If the backend reports out-of-memory.
        """
        try:
            return _complete(self._model, messages, max_tokens, temperature, seed, stream=False)
        except Exception as exc:
            _reraise_backend_error(exc)
            raise

    def stream(
        self,
        messages: Sequence[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
        seed: int | None,
    ) -> Iterator[str]:
        """Yield completion chunks.

        Args:
            messages: Chat messages in role/content form.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            seed: Optional generation seed.

        Yields:
            String chunks from the backend.

        Raises:
            GenerationError: If generation fails for a non-device reason.
            DeviceError: If the backend reports out-of-memory.
        """
        try:
            chunks = _complete(self._model, messages, max_tokens, temperature, seed, stream=True)
            assert isinstance(chunks, list)
            yield from chunks
        except Exception as exc:
            _reraise_backend_error(exc)
            raise


def _complete(
    model: object,
    messages: Sequence[dict[str, str]],
    max_tokens: int,
    temperature: float,
    seed: int | None,
    *,
    stream: bool,
) -> str | list[str]:
    """Run chat completion, falling back to raw completion when needed.

    Args:
        model: Instantiated ``llama_cpp.Llama`` object.
        messages: Chat messages.
        max_tokens: Maximum tokens to generate.
        temperature: Sampling temperature.
        seed: Optional generation seed.
        stream: Whether to collect streaming chunks.

    Returns:
        A string, or a list of chunks when ``stream`` is true.
    """
    kwargs: dict[str, object] = {
        "messages": list(messages),
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream,
    }
    if seed is not None:
        kwargs["seed"] = seed
    create_chat = model.create_chat_completion
    try:
        result = create_chat(**kwargs)
    except Exception:
        prompt = _messages_to_prompt(messages)
        completion_kwargs: dict[str, object] = {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if seed is not None:
            completion_kwargs["seed"] = seed
        result = model.create_completion(prompt, **completion_kwargs)
        return _parse_completion(result, stream=stream)
    return _parse_chat(result, stream=stream)


def _parse_chat(result: object, *, stream: bool) -> str | list[str]:
    """Extract text from a chat-completion payload.

    Args:
        result: Backend return value.
        stream: Whether the payload is an iterator of chunks.

    Returns:
        Assistant text or chunk list.
    """
    if stream:
        chunks: list[str] = []
        for item in result:  # type: ignore[union-attr]
            choice = _first_choice(item)
            delta = choice.get("delta", {}) if isinstance(choice, dict) else {}
            content = delta.get("content") if isinstance(delta, dict) else None
            if isinstance(content, str) and content:
                chunks.append(content)
        return chunks
    choice = _first_choice(result)
    message = choice.get("message", {}) if isinstance(choice, dict) else {}
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content
    return ""


def _parse_completion(result: object, *, stream: bool) -> str | list[str]:
    """Extract text from a raw completion payload.

    Args:
        result: Backend return value.
        stream: Whether the payload is an iterator of chunks.

    Returns:
        Completion text or chunk list.
    """
    if stream:
        chunks: list[str] = []
        for item in result:  # type: ignore[union-attr]
            choice = _first_choice(item)
            text = choice.get("text") if isinstance(choice, dict) else None
            if isinstance(text, str) and text:
                chunks.append(text)
        return chunks
    choice = _first_choice(result)
    text = choice.get("text") if isinstance(choice, dict) else None
    if isinstance(text, str):
        return text
    return ""


def _first_choice(payload: object) -> dict[str, object]:
    """Return the first choice mapping from a completion payload.

    Args:
        payload: Chat or completion result.

    Returns:
        The first choice dictionary, or an empty mapping.
    """
    if not isinstance(payload, dict):
        return {}
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        return choices[0]
    return {}


def _messages_to_prompt(messages: Sequence[dict[str, str]]) -> str:
    """Format chat messages as a plain prompt for models without a template.

    Args:
        messages: Chat messages.

    Returns:
        A simple role-prefixed prompt string.
    """
    lines = [f"{item.get('role', 'user').title()}: {item.get('content', '')}" for item in messages]
    lines.append("Assistant:")
    return "\n".join(lines)


def _reraise_backend_error(exc: BaseException) -> None:
    """Map a native backend exception to a public SDK error.

    Args:
        exc: Native exception raised by llama.cpp.

    Raises:
        DeviceError: If the message indicates out-of-memory.
        GenerationError: For other load or generate failures.
    """
    text = str(exc).lower()
    if any(token in text for token in ("out of memory", "oom", "failed to allocate")):
        raise DeviceError(
            "The GPU ran out of memory during local generation.",
            remediation=_OOM_REMEDIATION,
        ) from exc
    raise GenerationError(
        "Local generation failed.",
        remediation=_GENERATION_REMEDIATION,
    ) from exc
