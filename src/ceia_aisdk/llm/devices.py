"""Effective CPU/CUDA selection for local LLM generation."""

from __future__ import annotations

from ceia_aisdk._logging import get_logger
from ceia_aisdk.hardware import HardwareSnapshot, get_device, probe_gpus, select_device

_LOGGER = get_logger(__name__)
_VRAM_MARGIN = 0.9


def cuda_binding_present() -> bool:
    """Return whether the installed llama.cpp binding reports GPU offload.

    This helper imports ``llama_cpp`` only when called, and bounds that import
    so ``doctor`` stays inside the five-second CPU budget. Callers that must
    keep the package-root import budget must not invoke it from
    ``ceia_aisdk`` package import.

    Returns:
        True when the binding imports and exposes GPU offload support.
    """
    import importlib.util
    import threading

    if importlib.util.find_spec("llama_cpp") is None:
        return False
    result: list[bool] = [False]

    def _probe() -> None:
        try:
            import llama_cpp
        except ImportError:
            result[0] = False
            return
        supports = getattr(llama_cpp, "llama_supports_gpu_offload", None)
        if callable(supports):
            try:
                result[0] = bool(supports())
                return
            except Exception:
                result[0] = False
                return
        compiled = str(getattr(llama_cpp, "__file__", "")).lower()
        result[0] = "cuda" in compiled or bool(getattr(llama_cpp, "GGML_CUDA", False))

    thread = threading.Thread(target=_probe, daemon=True)
    thread.start()
    thread.join(timeout=1.0)
    if thread.is_alive():
        _LOGGER.warning("CUDA binding probe timed out; reporting cuda_binding=no")
        return False
    return result[0]


def resolve_generation_device(
    requested: str,
    *,
    size_gb: float | None = None,
    snapshot: HardwareSnapshot | None = None,
    binding_present: bool | None = None,
    apply_vram_fallback: bool = False,
) -> tuple[str, int]:
    """Select the effective generation device and ``n_gpu_layers``.

    Args:
        requested: Configured or constructor device string.
        size_gb: Cataloged on-disk size in gigabytes.
        snapshot: Optional hardware snapshot. When omitted, one probe runs.
        binding_present: Whether a CUDA-capable llama.cpp binding is installed.
            ``None`` skips the binding gate (CPU/auto only).
        apply_vram_fallback: When true, ``device="auto"`` falls back to CPU if
            ``size_gb`` exceeds 90 percent of free VRAM.

    Returns:
        ``(cpu|cuda:N, n_gpu_layers)`` where ``n_gpu_layers`` is ``0`` or ``-1``.

    Raises:
        DeviceError: If an explicit CUDA request cannot be satisfied.
    """
    effective_snapshot = snapshot if snapshot is not None else probe_gpus(requested=requested)
    selected = select_device(requested, effective_snapshot)
    if requested == "cpu" or selected == "cpu":
        return "cpu", 0
    if binding_present is False:
        if requested.startswith("cuda"):
            from ceia_aisdk.errors import DeviceError

            raise DeviceError(
                "CUDA was requested but the CUDA inference binding is not present.",
                remediation=(
                    'Install ceia-aisdk[cuda] with a CUDA llama-cpp-python, or use device="cpu".'
                ),
            )
        _LOGGER.warning("A GPU is visible but the CUDA inference binding is missing; using cpu")
        return "cpu", 0
    if (
        apply_vram_fallback
        and requested == "auto"
        and size_gb is not None
        and _exceeds_vram_margin(selected, size_gb, effective_snapshot)
    ):
        _LOGGER.warning("Model size_gb exceeds 90 percent of free GPU memory; falling back to cpu")
        return "cpu", 0
    if (
        requested.startswith("cuda")
        and size_gb is not None
        and _exceeds_vram_margin(selected, size_gb, effective_snapshot)
    ):
        from ceia_aisdk.errors import DeviceError

        raise DeviceError(
            "The selected CUDA device does not have enough free memory for this alias.",
            remediation='Use llm/small or set device="cpu".',
        )
    if selected.startswith("cuda"):
        _LOGGER.info("Using %s for local generation", selected)
        return selected, -1
    return "cpu", 0


def _exceeds_vram_margin(selected: str, size_gb: float, snapshot: HardwareSnapshot) -> bool:
    """Return whether catalog size exceeds 90 percent of free VRAM.

    Args:
        selected: Selected ``cuda:N`` device.
        size_gb: Cataloged size in gigabytes.
        snapshot: Hardware snapshot with GPU memory.

    Returns:
        True when the alias does not fit under the margin.
    """
    if not selected.startswith("cuda:"):
        return False
    index = int(selected.split(":", 1)[1])
    matching = [gpu for gpu in snapshot.gpus if gpu.index == index]
    if not matching:
        return True
    free_gb = matching[0].free_vram_mib / 1024.0
    return size_gb > _VRAM_MARGIN * free_gb


def select_requested_device(requested: str) -> str:
    """Select ``cpu`` or ``cuda:N`` using the public hardware helper.

    Args:
        requested: Requested device string.

    Returns:
        ``cpu`` or ``cuda:N``.

    Raises:
        DeviceError: If an explicit CUDA target cannot be selected.
    """
    return get_device(requested)
