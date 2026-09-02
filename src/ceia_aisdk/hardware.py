"""Bounded NVIDIA probing and CPU/CUDA device selection."""

from __future__ import annotations

import csv
import io
import os
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Final

from ceia_aisdk._logging import get_logger
from ceia_aisdk.errors import DeviceError

_LOGGER = get_logger(__name__)

NVIDIA_SMI_TIMEOUT_SECONDS: Final[int] = 2
NVIDIA_SMI_ARGS: Final[tuple[str, ...]] = (
    "nvidia-smi",
    "--query-gpu=index,uuid,name,memory.total,memory.free,compute_mode,mig.mode.current",
    "--format=csv,noheader,nounits",
)
_MAX_PROBE_CHARS = 1_000_000
_DEVICE_CPU = "cpu"
_DEVICE_AUTO = "auto"
_DEVICE_CUDA = "cuda"


class ProbeStatus(Enum):
    """Outcome of a single NVIDIA probe attempt."""

    NOT_RUN = "not_run"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class GPUInfo:
    """Public non-sensitive NVIDIA GPU observation.

    Attributes:
        index: Local ``nvidia-smi``/NVML index.
        name: Nonempty display name.
        total_vram_mib: Total memory in MiB.
        free_vram_mib: Free memory in MiB.
    """

    index: int
    name: str
    total_vram_mib: int
    free_vram_mib: int

    def __post_init__(self) -> None:
        """Validate public GPU invariants.

        Raises:
            ValueError: If identifiers or memory values are inconsistent.
        """
        if self.index < 0:
            raise ValueError("GPU index must be nonnegative")
        if not self.name.strip():
            raise ValueError("GPU name must be nonempty")
        if self.total_vram_mib < 0 or self.free_vram_mib < 0:
            raise ValueError("GPU memory values must be nonnegative")
        if self.free_vram_mib > self.total_vram_mib:
            raise ValueError("free_vram_mib must be <= total_vram_mib")


@dataclass(frozen=True, slots=True)
class _ProbeRecord:
    """Internal NVIDIA probe row, including non-public identifiers."""

    index: int
    uuid: str
    name: str
    total_vram_mib: int
    free_vram_mib: int
    compute_mode: str
    mig_mode: str
    usable: bool

    def to_gpu_info(self) -> GPUInfo:
        """Convert to the public GPU value object.

        Returns:
            A ``GPUInfo`` instance without UUID, compute, or MIG fields.
        """
        return GPUInfo(
            index=self.index,
            name=self.name,
            total_vram_mib=self.total_vram_mib,
            free_vram_mib=self.free_vram_mib,
        )


@dataclass(frozen=True, slots=True)
class HardwareSnapshot:
    """One bounded hardware observation used for selection and diagnostics.

    Attributes:
        gpus: Detected GPUs sorted by index.
        usable_gpu_indices: Sorted indices eligible for selection.
        probe_status: Whether the NVIDIA probe ran and whether it is trusted.
        probe_detail: Privacy-safe failure detail, if any.
    """

    gpus: tuple[GPUInfo, ...]
    usable_gpu_indices: tuple[int, ...]
    probe_status: ProbeStatus
    probe_detail: str | None


Runner = Callable[[], subprocess.CompletedProcess[str]]


def probe_gpus(*, requested: str, runner: Runner | None = None) -> HardwareSnapshot:
    """Collect one NVIDIA snapshot, or skip probing for ``cpu``.

    Args:
        requested: Requested device string from configuration or callers.
        runner: Optional test double that returns a completed ``nvidia-smi``
            process. When omitted, one local subprocess is executed.

    Returns:
        An immutable hardware snapshot. Probe failures never raise.
    """
    if requested == _DEVICE_CPU:
        return HardwareSnapshot((), (), ProbeStatus.NOT_RUN, None)
    try:
        completed = (runner or _run_nvidia_smi)()
    except FileNotFoundError:
        _LOGGER.debug("nvidia-smi was not found")
        return _failed_snapshot("nvidia-smi was not found on PATH")
    except subprocess.TimeoutExpired:
        _LOGGER.debug("nvidia-smi timed out after %s seconds", NVIDIA_SMI_TIMEOUT_SECONDS)
        return _failed_snapshot("nvidia-smi timed out")
    except OSError:
        _LOGGER.debug("nvidia-smi could not be executed", exc_info=True)
        return _failed_snapshot("nvidia-smi could not be executed")
    if completed.returncode != 0:
        return _failed_snapshot("nvidia-smi exited with an error")
    stdout = completed.stdout or ""
    if len(stdout) > _MAX_PROBE_CHARS:
        return _failed_snapshot("nvidia-smi output exceeded the trusted size limit")
    try:
        records = _parse_probe_csv(stdout)
    except ValueError:
        return _failed_snapshot("nvidia-smi returned an untrusted snapshot")
    gpus = tuple(record.to_gpu_info() for record in records)
    usable = tuple(record.index for record in records if record.usable)
    return HardwareSnapshot(gpus, usable, ProbeStatus.SUCCEEDED, None)


def select_device(requested: str, snapshot: HardwareSnapshot) -> str:
    """Select ``cpu`` or ``cuda:N`` from a requested device and snapshot.

    Args:
        requested: Requested device string.
        snapshot: Previously collected hardware snapshot.

    Returns:
        ``cpu`` or ``cuda:N``.

    Raises:
        DeviceError: If the request is invalid or an explicit CUDA target is
            unavailable.
    """
    if requested == _DEVICE_CPU:
        return _DEVICE_CPU
    if requested == _DEVICE_AUTO:
        if snapshot.usable_gpu_indices:
            selected = f"cuda:{snapshot.usable_gpu_indices[0]}"
            _LOGGER.debug("Selected %s from auto", selected)
            return selected
        _LOGGER.info("No usable NVIDIA GPU; using cpu")
        return _DEVICE_CPU
    if requested == _DEVICE_CUDA:
        if snapshot.usable_gpu_indices:
            return f"cuda:{snapshot.usable_gpu_indices[0]}"
        raise DeviceError(
            "CUDA was requested but no usable NVIDIA GPU is available.",
            remediation='Use device="cpu" or install a working NVIDIA driver and nvidia-smi.',
        )
    index = _parse_cuda_index(requested)
    if index is None:
        raise DeviceError(
            "The requested device syntax is invalid.",
            remediation=(
                'Use device="cpu", device="cuda", or device="cuda:N" with a '
                "canonical nonnegative index."
            ),
        )
    if index in snapshot.usable_gpu_indices:
        return f"cuda:{index}"
    raise DeviceError(
        f"CUDA index {index} is not available.",
        remediation='Use device="cpu", omit the index, or choose an index reported by nvidia-smi.',
    )


def detect_gpus() -> tuple[GPUInfo, ...]:
    """Detect local NVIDIA GPUs without loading an inference backend.

    Returns:
        GPU records sorted by ascending index. The tuple is empty when no GPU
        is available or the bounded probe is untrusted.
    """
    snapshot = probe_gpus(requested=_DEVICE_AUTO)
    return snapshot.gpus


def get_device(device: str = "auto") -> str:
    """Select ``cpu`` or ``cuda:N`` from a requested device.

    Args:
        device: ``auto``, ``cpu``, ``cuda``, or ``cuda:N``. ``cpu`` skips the
            NVIDIA probe.

    Returns:
        ``cpu`` or ``cuda:N``.

    Raises:
        DeviceError: If ``device`` is invalid or an explicit CUDA target cannot
            be selected.
    """
    snapshot = probe_gpus(requested=device)
    return select_device(device, snapshot)


def _run_nvidia_smi() -> subprocess.CompletedProcess[str]:
    """Execute the fixed NVIDIA query with a two-second timeout.

    Returns:
        The completed process result.

    Raises:
        FileNotFoundError: If ``nvidia-smi`` is not on PATH.
        subprocess.TimeoutExpired: If the process exceeds the timeout.
        OSError: If the process cannot be started.
    """
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return subprocess.run(
        list(NVIDIA_SMI_ARGS),
        check=False,
        capture_output=True,
        text=True,
        timeout=NVIDIA_SMI_TIMEOUT_SECONDS,
        shell=False,
        stdin=subprocess.DEVNULL,
        env=env,
    )


def _failed_snapshot(detail: str) -> HardwareSnapshot:
    """Return a failed snapshot with a sanitized detail string.

    Args:
        detail: Privacy-safe reason for the failure.

    Returns:
        A snapshot with no GPU records.
    """
    return HardwareSnapshot((), (), ProbeStatus.FAILED, detail)


def _parse_probe_csv(text: str) -> tuple[_ProbeRecord, ...]:
    """Parse bounded ``nvidia-smi`` CSV into internal records.

    Args:
        text: CSV body using ``noheader,nounits``.

    Returns:
        Records sorted by numeric index.

    Raises:
        ValueError: If any row is malformed, duplicated, or inconsistent.
    """
    if not text.strip():
        return ()
    reader = csv.reader(io.StringIO(text), skipinitialspace=True)
    records: list[_ProbeRecord] = []
    seen: set[int] = set()
    for raw_row in reader:
        if not raw_row or all(not cell.strip() for cell in raw_row):
            continue
        if len(raw_row) != 7:
            raise ValueError("expected seven CSV fields")
        record = _record_from_row(tuple(cell.strip() for cell in raw_row))
        if record.index in seen:
            raise ValueError("duplicate GPU index")
        seen.add(record.index)
        records.append(record)
    records.sort(key=lambda item: item.index)
    return tuple(records)


def _record_from_row(row: Sequence[str]) -> _ProbeRecord:
    """Validate one CSV row.

    Args:
        row: Seven stripped CSV fields.

    Returns:
        An internal probe record.

    Raises:
        ValueError: If the row cannot be trusted.
    """
    index_text, uuid, name, total_text, free_text, compute_mode, mig_mode = row
    if not index_text.isdigit():
        raise ValueError("index must be a nonnegative integer")
    index = int(index_text)
    if not uuid or not name:
        raise ValueError("uuid and name must be nonempty")
    try:
        total = int(total_text)
        free = int(free_text)
    except ValueError as exc:
        raise ValueError("memory values must be integers") from exc
    if total < 0 or free < 0 or free > total:
        raise ValueError("memory values are inconsistent")
    usable = _is_usable(compute_mode, mig_mode)
    return _ProbeRecord(
        index=index,
        uuid=uuid,
        name=name,
        total_vram_mib=total,
        free_vram_mib=free,
        compute_mode=compute_mode,
        mig_mode=mig_mode,
        usable=usable,
    )


def _is_usable(compute_mode: str, mig_mode: str) -> bool:
    """Return whether a GPU may be selected in PRD-00.

    Args:
        compute_mode: NVIDIA compute mode string.
        mig_mode: Current MIG mode string.

    Returns:
        True when compute is not prohibited and MIG is not enabled.
    """
    if compute_mode.strip().lower() == "prohibited":
        return False
    return mig_mode.strip().lower() not in {"enabled", "enable"}


def _parse_cuda_index(requested: str) -> int | None:
    """Parse ``cuda:N`` into an index.

    Args:
        requested: Device string.

    Returns:
        The index, or ``None`` when the syntax is invalid.
    """
    prefix = "cuda:"
    if not requested.startswith(prefix):
        return None
    rest = requested[len(prefix) :]
    if rest == "0":
        return 0
    if rest.isdigit() and not rest.startswith("0"):
        return int(rest)
    return None
