"""Synchronous local LLM constructor and generation methods.

Instances of ``LLM`` are not thread-safe. Concurrent use from more than one
thread is undefined, and this module does not install a process-wide lock.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator, Sequence
from typing import TYPE_CHECKING

from ceia_aisdk._logging import get_logger
from ceia_aisdk.config import AISDKConfig
from ceia_aisdk.errors import AISDKError, GenerationError
from ceia_aisdk.llm.backend import InferenceBackend, create_backend
from ceia_aisdk.llm.devices import resolve_generation_device
from ceia_aisdk.llm.settings import LLMSettings
from ceia_aisdk.llm.tools import ToolDeclaration
from ceia_aisdk.registry import ensure_local, get_public_metadata, resolve

if TYPE_CHECKING:
    from ceia_aisdk.llm.session import Session

_LOGGER = get_logger(__name__)
_DOMAIN = "llm"


class LLM:
    """Local GGUF chat wrapper bound to one alias and one device.

    Instances are not thread-safe. Do not share one ``LLM`` across threads.
    Model weights are obtained through the registry cache and are not bundled
    in the wheel.
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
        """Construct a local generator for one cataloged alias.

        The instance is not thread-safe. ``llama_cpp`` is imported only after
        ``ensure_local`` returns a verified file. Offline cache misses raise
        ``DownloadError`` without loading the inference binding.

        Args:
            alias: Cataloged alias or unqualified size. ``None`` uses
                ``LLMSettings.default_alias`` (``llm/small@latest`` by default).
            config: Effective SDK configuration. Defaults to ``AISDKConfig.load()``.
            device: Per-instance device override. Defaults to ``config.device``.
            context_length: Per-instance context window override.
            tools: Optional tool declarations. Rejected when the alias lacks
                ``tool_use``.

        Raises:
            ConfigError: If LLM settings or core configuration are invalid.
            ModelNotFoundError: If the alias is not in the active catalog.
            DownloadError: If the artifact cannot be obtained.
            DeviceError: If an explicit CUDA device cannot be used.
            CapabilityError: If tools are passed to an alias without ``tool_use``.
            GenerationError: If the local runtime cannot load the file.
        """
        self._config = config if config is not None else AISDKConfig.load()
        self._settings = LLMSettings.load(
            default_alias=alias,
            context_length=context_length,
        )
        requested_alias = alias if alias is not None else self._settings.default_alias
        domain = None if "/" in requested_alias else _DOMAIN
        resolved = resolve(requested_alias, config=self._config, domain=domain)
        progress, stop_progress = _tty_progress()
        try:
            self._path = ensure_local(
                requested_alias,
                config=self._config,
                domain=domain,
                progress=progress,
            )
        finally:
            stop_progress()
        metadata = get_public_metadata(requested_alias, config=self._config, domain=domain)
        self._tools = tuple(tools) if tools else ()
        if self._tools:
            from ceia_aisdk.errors import CapabilityError

            if "tool_use" not in metadata.capabilities:
                raise CapabilityError(
                    "The selected alias does not support tool use.",
                    remediation=(
                        "Choose an alias whose public capabilities include tool_use, "
                        "for example llm/medium when that capability is cataloged."
                    ),
                )
        requested_device = device if device is not None else self._config.device
        binding_present = None
        if requested_device != "cpu":
            from ceia_aisdk.llm.devices import cuda_binding_present

            binding_present = cuda_binding_present()
        effective, n_gpu_layers = resolve_generation_device(
            requested_device,
            size_gb=metadata.size_gb,
            binding_present=binding_present,
            apply_vram_fallback=True,
        )
        self._alias = resolved.alias
        self._device = effective
        self._n_gpu_layers = n_gpu_layers
        self._n_ctx = min(self._settings.context_length, metadata.context_length)
        if effective.startswith("cuda"):
            _LOGGER.info("Generating on %s", effective)
        self._backend: InferenceBackend = create_backend(
            self._path,
            n_ctx=self._n_ctx,
            n_gpu_layers=n_gpu_layers,
        )

    @property
    def alias(self) -> str:
        """Return the canonical catalog alias.

        Returns:
            Canonical ``domain/size@N`` string after resolve.
        """
        return self._alias

    @property
    def device(self) -> str:
        """Return the effective generation device.

        Returns:
            ``cpu`` or ``cuda:N``.
        """
        return self._device

    def chat(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> str:
        """Generate a one-shot completion. History is not retained.

        Args:
            prompt: User prompt text.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            seed: Optional generation seed.

        Returns:
            Assistant text. The smoke prompt ``Say only: ok`` yields a nonempty
            string on a working local model.

        Raises:
            GenerationError: If generation fails for a non-device reason.
            DeviceError: If the backend reports out-of-memory.
        """
        messages = [{"role": "user", "content": prompt}]
        try:
            text = self._backend.generate(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                seed=seed,
            )
        except AISDKError:
            raise
        except Exception as exc:
            from ceia_aisdk.llm.backend import _reraise_backend_error

            _reraise_backend_error(exc)
            raise
        if not isinstance(text, str) or not text.strip():
            raise GenerationError(
                "Local generation returned an empty completion.",
                remediation="Retry with a shorter prompt or a different alias.",
            )
        return text

    def stream(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> Iterator[str]:
        """Yield completion chunks from the same path as ``chat``.

        Args:
            prompt: User prompt text.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            seed: Optional generation seed.

        Yields:
            String chunks. Concatenation equals ``chat`` when the backend is
            bit-stable under ``temperature=0`` and a fixed seed; otherwise at
            least one chunk and nonempty final text are produced.

        Raises:
            GenerationError: If generation fails for a non-device reason.
            DeviceError: If the backend reports out-of-memory.
        """
        messages = [{"role": "user", "content": prompt}]
        yielded = False
        try:
            stream_iter = self._backend.stream(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                seed=seed,
            )
            for chunk in stream_iter:
                yielded = True
                yield chunk
        except AISDKError:
            raise
        except Exception as exc:
            from ceia_aisdk.llm.backend import _reraise_backend_error

            _reraise_backend_error(exc)
            raise
        if not yielded:
            text = self.chat(prompt, max_tokens=max_tokens, temperature=temperature, seed=seed)
            yield text

    def session(self, system: str | None = None) -> Session:
        """Return a multi-turn session bound to this instance.

        Args:
            system: Optional system prompt retained for the session.

        Returns:
            A ``Session`` that is not thread-safe.
        """
        from ceia_aisdk.llm.session import Session

        return Session(self, system=system)


def _tty_progress() -> tuple[
    Callable[[int, int | None], None] | None,
    Callable[[], None],
]:
    """Return a Rich progress callback when stderr is a TTY.

    Returns:
        A ``(callback, stop)`` pair. ``callback`` is ``None`` when stderr is
        not a TTY.
    """
    if not sys.stderr.isatty():
        return None, lambda: None
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        TextColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )

    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=Console(file=sys.stderr),
        transient=True,
    )
    progress.start()
    task_id = progress.add_task("Downloading", total=None)

    def _update(have: int, total: int | None) -> None:
        progress.update(task_id, completed=have, total=total)

    def _stop() -> None:
        progress.stop()

    return _update, _stop
