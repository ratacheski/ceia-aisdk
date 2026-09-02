"""Diagnostic collection and rendering for ``ceia-aisdk doctor``."""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ceia_aisdk import __version__
from ceia_aisdk.config import AISDKConfig
from ceia_aisdk.errors import ConfigError, DeviceError
from ceia_aisdk.hardware import GPUInfo, HardwareSnapshot, ProbeStatus

COPY_BLOCK_BEGIN = "--- CEIA AI SDK doctor: copy this ---"
COPY_BLOCK_END = "--- end CEIA AI SDK doctor ---"
_OPTIONAL_GROUPS = ("cuda:reserved",)


class CheckStatus(Enum):
    """Readiness status for one diagnostic check."""

    PASS = "pass"
    INFO = "info"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    """One machine-readiness observation.

    Attributes:
        key: Stable internal identifier.
        label: English display label.
        status: Pass, info, or fail.
        summary: Privacy-safe value or explanation.
        remediation: Required next action when ``status`` is fail.
    """

    key: str
    label: str
    status: CheckStatus
    summary: str
    remediation: str | None = None

    def __post_init__(self) -> None:
        """Enforce failed-check remediation.

        Raises:
            ValueError: If a failed check has empty remediation.
        """
        if self.status is CheckStatus.FAIL and not (self.remediation and self.remediation.strip()):
            raise ValueError("failed diagnostic checks require nonempty remediation")


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    """Immutable diagnostic snapshot consumed by every renderer.

    Attributes:
        operating_system: OS family name.
        architecture: Machine architecture.
        python_version: Running interpreter version.
        python_supported: Whether the version is in 3.11-3.13.
        package_version: Installed SDK version.
        package_importable: Whether the package imported successfully.
        configured_device: Requested device, if configuration loaded.
        effective_device: Selected device, if selection succeeded.
        gpus: Detected public GPU records.
        cache_dir: Home-normalized cache path.
        offline: Offline flag, if configuration loaded.
        optional_groups: Declared extra groups with reservation notes.
        checks: Deterministic readiness checks.
        usable: True when the foundation can be used.
        exit_code: Process exit code implied by ``usable``.
    """

    operating_system: str
    architecture: str
    python_version: str
    python_supported: bool
    package_version: str
    package_importable: bool
    configured_device: str | None
    effective_device: str | None
    gpus: tuple[GPUInfo, ...]
    cache_dir: str | None
    offline: bool | None
    optional_groups: tuple[str, ...]
    checks: tuple[DiagnosticCheck, ...]
    usable: bool
    exit_code: int


def normalize_user_path(path: Path) -> str:
    """Replace a home-directory prefix with ``~``.

    Args:
        path: Absolute or expanded user path.

    Returns:
        A POSIX path using ``~`` when the path is inside the home directory.
    """
    home = Path.home()
    try:
        relative = path.relative_to(home)
    except ValueError:
        return _single_line(path.as_posix())
    if str(relative) == ".":
        return "~"
    return _single_line(f"~/{relative.as_posix()}")


def build_report(
    *,
    config: AISDKConfig | None,
    snapshot: HardwareSnapshot,
    effective_device: str | None = None,
    selection_error: DeviceError | None = None,
    config_error: ConfigError | None = None,
) -> DiagnosticReport:
    """Build a complete diagnostic report from already collected inputs.

    Args:
        config: Loaded configuration, or ``None`` when loading failed.
        snapshot: Hardware snapshot collected for this run.
        effective_device: Selected device, if any.
        selection_error: Device selection failure, if any.
        config_error: Configuration loading failure, if any.

    Returns:
        An immutable report. Renderers must not change its outcome.
    """
    python_supported = _python_supported()
    package_importable = True
    checks = _build_checks(
        python_supported=python_supported,
        package_importable=package_importable,
        config=config,
        snapshot=snapshot,
        effective_device=effective_device,
        selection_error=selection_error,
        config_error=config_error,
    )
    usable = (
        python_supported and package_importable and config_error is None and selection_error is None
    )
    return DiagnosticReport(
        operating_system=_single_line(platform.system() or "unknown"),
        architecture=_single_line(platform.machine() or "unknown"),
        python_version=_single_line(platform.python_version()),
        python_supported=python_supported,
        package_version=_single_line(__version__),
        package_importable=package_importable,
        configured_device=None if config is None else config.device,
        effective_device=effective_device,
        gpus=() if snapshot.probe_status is ProbeStatus.FAILED else snapshot.gpus,
        cache_dir=None if config is None else normalize_user_path(config.cache_dir),
        offline=None if config is None else config.offline,
        optional_groups=_OPTIONAL_GROUPS,
        checks=checks,
        usable=usable,
        exit_code=0 if usable else 1,
    )


def format_copy_block(report: DiagnosticReport) -> str:
    """Serialize the fixed-order copyable ASCII block.

    Args:
        report: Diagnostic report.

    Returns:
        A newline-terminated block with no ANSI sequences.
    """
    failed = [check for check in report.checks if check.status is CheckStatus.FAIL]
    passed = sum(1 for check in report.checks if check.status is CheckStatus.PASS)
    remediation = "none"
    if failed:
        remediation = _single_line(
            "; ".join(check.remediation or check.summary for check in failed)
        )
    fields = [
        ("status", "usable" if report.usable else "unusable"),
        ("os", report.operating_system),
        ("architecture", report.architecture),
        ("python", report.python_version),
        ("python_supported", _flag(report.python_supported)),
        ("sdk_version", report.package_version),
        ("sdk_importable", _flag(report.package_importable)),
        ("configured_device", report.configured_device or "unavailable"),
        ("effective_device", report.effective_device or "unavailable"),
        ("gpus", _gpu_summary(report.gpus)),
        ("cache_dir", report.cache_dir or "unavailable"),
        ("offline", "unavailable" if report.offline is None else _flag(report.offline)),
        ("optional_groups", "cuda:reserved"),
        ("checks", f"{passed}/{len(report.checks)}"),
        ("exit_code", str(report.exit_code)),
        ("remediation", remediation),
    ]
    lines = [
        COPY_BLOCK_BEGIN,
        *[f"{key}={_single_line(value)}" for key, value in fields],
        COPY_BLOCK_END,
    ]
    return "\n".join(lines) + "\n"


def format_plain_report(report: DiagnosticReport) -> str:
    """Render a deterministic plain-text report without ANSI sequences.

    Args:
        report: Diagnostic report.

    Returns:
        Human-readable plain text including individual checks.
    """
    lines = [
        f"status: {'usable' if report.usable else 'unusable'}",
        f"operating_system: {report.operating_system}",
        f"architecture: {report.architecture}",
        f"python: {report.python_version} (supported={_flag(report.python_supported)})",
        f"sdk_version: {report.package_version} (importable={_flag(report.package_importable)})",
        f"configured_device: {report.configured_device or 'unavailable'}",
        f"effective_device: {report.effective_device or 'unavailable'}",
        f"gpus: {_gpu_summary(report.gpus)}",
        f"cache_dir: {report.cache_dir or 'unavailable'}",
        f"offline: {'unavailable' if report.offline is None else _flag(report.offline)}",
        f"optional_groups: {', '.join(report.optional_groups)}",
    ]
    for check in report.checks:
        line = f"check {check.key}: {check.status.value} {check.summary}"
        if check.remediation:
            line += f" ; remediation: {check.remediation}"
        lines.append(_single_line(line))
    lines.append(f"exit_code: {report.exit_code}")
    return "\n".join(lines) + "\n"


def render_report(report: DiagnosticReport, *, stdout: object, stderr: object) -> None:
    """Write interactive or plain output plus the copyable block.

    Args:
        report: Diagnostic report.
        stdout: Output stream, typically ``sys.stdout``.
        stderr: Error stream used for failed remediations.
    """
    interactive = _is_interactive(stdout)
    if interactive:
        _render_rich(report, stdout)
    else:
        stdout.write(format_plain_report(report))
    stdout.write(format_copy_block(report))
    if not report.usable:
        failed = [check for check in report.checks if check.status is CheckStatus.FAIL]
        if failed and failed[0].remediation:
            stderr.write(_single_line(failed[0].remediation) + "\n")


def _build_checks(
    *,
    python_supported: bool,
    package_importable: bool,
    config: AISDKConfig | None,
    snapshot: HardwareSnapshot,
    effective_device: str | None,
    selection_error: DeviceError | None,
    config_error: ConfigError | None,
) -> tuple[DiagnosticCheck, ...]:
    """Compose deterministic checks in stable order.

    Args:
        python_supported: Python version gate.
        package_importable: Package import gate.
        config: Loaded configuration if any.
        snapshot: Hardware snapshot.
        effective_device: Selected device if any.
        selection_error: Device error if any.
        config_error: Configuration error if any.

    Returns:
        Ordered diagnostic checks.
    """
    checks: list[DiagnosticCheck] = [
        DiagnosticCheck(
            key="python",
            label="Python version",
            status=CheckStatus.PASS if python_supported else CheckStatus.FAIL,
            summary=platform.python_version(),
            remediation=None
            if python_supported
            else "Install Python 3.11, 3.12, or 3.13 and recreate the environment with uv.",
        ),
        DiagnosticCheck(
            key="package",
            label="SDK package",
            status=CheckStatus.PASS if package_importable else CheckStatus.FAIL,
            summary=f"ceia-aisdk {__version__}",
            remediation=None
            if package_importable
            else "Install ceia-aisdk from this repository with uv.",
        ),
    ]
    if config_error is not None:
        checks.append(
            DiagnosticCheck(
                key="configuration",
                label="Configuration",
                status=CheckStatus.FAIL,
                summary=_single_line(str(config_error)),
                remediation=_single_line(config_error.remediation),
            )
        )
    elif selection_error is not None:
        checks.append(
            DiagnosticCheck(
                key="device",
                label="Device selection",
                status=CheckStatus.FAIL,
                summary=_single_line(str(selection_error)),
                remediation=_single_line(selection_error.remediation),
            )
        )
    else:
        checks.append(
            DiagnosticCheck(
                key="device",
                label="Device selection",
                status=CheckStatus.PASS,
                summary=_single_line(
                    effective_device or (config.device if config else "unavailable")
                ),
            )
        )
    gpu_summary = _gpu_summary(
        snapshot.gpus if snapshot.probe_status is ProbeStatus.SUCCEEDED else ()
    )
    if snapshot.probe_status is ProbeStatus.FAILED:
        gpu_summary = _single_line(snapshot.probe_detail or "NVIDIA probe failed")
    checks.append(
        DiagnosticCheck(
            key="gpus",
            label="GPUs",
            status=CheckStatus.INFO,
            summary=gpu_summary,
        )
    )
    checks.append(
        DiagnosticCheck(
            key="optional_groups",
            label="Optional groups",
            status=CheckStatus.INFO,
            summary="cuda is reserved and does not install a runtime in this feature",
        )
    )
    return tuple(checks)


def _python_supported() -> bool:
    """Return whether the running interpreter is in the supported range.

    Returns:
        True for Python 3.11, 3.12, or 3.13.
    """
    return sys.version_info >= (3, 11) and sys.version_info < (3, 14)


def _gpu_summary(gpus: tuple[GPUInfo, ...]) -> str:
    """Return a bounded single-line GPU summary.

    Args:
        gpus: Public GPU records.

    Returns:
        ``none`` or a semicolon-separated index/name/memory summary.
    """
    if not gpus:
        return "none"
    parts = [f"{gpu.index}:{gpu.name}:{gpu.total_vram_mib}/{gpu.free_vram_mib}" for gpu in gpus]
    return _single_line("; ".join(parts))


def _flag(value: bool) -> str:
    """Format a boolean as lowercase text.

    Args:
        value: Boolean value.

    Returns:
        ``true`` or ``false``.
    """
    return "true" if value else "false"


def _single_line(value: str) -> str:
    """Remove control characters and collapse a value onto one line.

    Args:
        value: Raw string.

    Returns:
        A sanitized single-line string.
    """
    cleaned = "".join(ch if ch >= " " and ch != "\x7f" else " " for ch in value)
    return " ".join(cleaned.split())


def _is_interactive(stream: object) -> bool:
    """Return whether Rich interactive rendering should be used.

    Args:
        stream: Output stream.

    Returns:
        True when the stream is a TTY and color is not disabled.
    """
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    isatty = getattr(stream, "isatty", None)
    return bool(isatty()) if callable(isatty) else False


def _render_rich(report: DiagnosticReport, stdout: object) -> None:
    """Render an interactive Rich report.

    Args:
        report: Diagnostic report.
        stdout: Terminal stream.
    """
    from rich.console import Console
    from rich.table import Table

    width = _terminal_width()
    console = Console(file=stdout, width=width, highlight=False, soft_wrap=True)
    table = Table(title="CEIA AI SDK doctor", show_header=True)
    table.add_column("Field", overflow="fold")
    table.add_column("Value", overflow="fold")
    table.add_row("status", "usable" if report.usable else "unusable")
    table.add_row("operating_system", report.operating_system)
    table.add_row("architecture", report.architecture)
    table.add_row("python", f"{report.python_version} supported={_flag(report.python_supported)}")
    table.add_row(
        "sdk_version", f"{report.package_version} importable={_flag(report.package_importable)}"
    )
    table.add_row("configured_device", report.configured_device or "unavailable")
    table.add_row("effective_device", report.effective_device or "unavailable")
    table.add_row("gpus", _gpu_summary(report.gpus))
    table.add_row("cache_dir", report.cache_dir or "unavailable")
    table.add_row("offline", "unavailable" if report.offline is None else _flag(report.offline))
    table.add_row("optional_groups", ", ".join(report.optional_groups))
    for check in report.checks:
        value = f"{check.status.value} {check.summary}"
        if check.remediation:
            value += f" | {check.remediation}"
        table.add_row(check.label, value)
    console.print(table)


def _terminal_width() -> int:
    """Return a representative terminal width.

    Returns:
        Width from ``COLUMNS`` or 80.
    """
    raw = os.environ.get("COLUMNS")
    if raw and raw.isdigit():
        return max(40, int(raw))
    return 80
