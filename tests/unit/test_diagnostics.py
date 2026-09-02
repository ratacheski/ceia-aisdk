"""Unit tests for diagnostic reports, copy blocks, and privacy."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from ceia_aisdk._diagnostics import (
    COPY_BLOCK_BEGIN,
    COPY_BLOCK_END,
    CheckStatus,
    DiagnosticCheck,
    DiagnosticReport,
    build_report,
    format_copy_block,
    format_plain_report,
    normalize_user_path,
)
from ceia_aisdk.config import AISDKConfig
from ceia_aisdk.errors import DeviceError
from ceia_aisdk.hardware import GPUInfo, HardwareSnapshot, ProbeStatus


def _config(isolated_home: Path, **overrides: object) -> AISDKConfig:
    values = {
        "device": "cpu",
        "cache_dir": isolated_home / ".ceia-aisdk",
        "log_level": "WARNING",
        "offline": False,
    }
    values.update(overrides)
    return AISDKConfig(**values)  # type: ignore[arg-type]


def _cpu_snapshot() -> HardwareSnapshot:
    return HardwareSnapshot(
        gpus=(),
        usable_gpu_indices=(),
        probe_status=ProbeStatus.NOT_RUN,
        probe_detail=None,
    )


def test_checks_and_reports_are_immutable(isolated_home: Path) -> None:
    report = build_report(
        config=_config(isolated_home),
        snapshot=_cpu_snapshot(),
        effective_device="cpu",
    )
    assert dataclasses.is_dataclass(DiagnosticReport)
    assert dataclasses.is_dataclass(DiagnosticCheck)
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        report.usable = False  # type: ignore[misc]
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        report.checks[0].summary = "nope"  # type: ignore[misc]


def test_cpu_report_is_usable(isolated_home: Path) -> None:
    report = build_report(
        config=_config(isolated_home),
        snapshot=_cpu_snapshot(),
        effective_device="cpu",
    )
    assert report.usable is True
    assert report.exit_code == 0
    assert report.effective_device == "cpu"
    assert report.configured_device == "cpu"
    assert report.optional_groups == ("cuda",)
    assert report.cuda_binding is False
    assert report.python_supported is True
    assert report.package_importable is True
    assert all(check.status != CheckStatus.FAIL for check in report.checks)


def test_forced_cuda_failure_is_unusable(isolated_home: Path) -> None:
    error = DeviceError(
        "Requested CUDA device is unavailable.",
        remediation="Use device=cpu or install a working NVIDIA driver and nvidia-smi.",
    )
    report = build_report(
        config=_config(isolated_home, device="cuda"),
        snapshot=HardwareSnapshot(
            gpus=(),
            usable_gpu_indices=(),
            probe_status=ProbeStatus.FAILED,
            probe_detail="nvidia-smi was not found",
        ),
        effective_device=None,
        selection_error=error,
    )
    assert report.usable is False
    assert report.exit_code == 1
    assert report.effective_device is None
    failed = [check for check in report.checks if check.status == CheckStatus.FAIL]
    assert failed
    assert all(check.remediation for check in failed)


def test_copy_block_field_order_and_values(isolated_home: Path) -> None:
    report = build_report(
        config=_config(isolated_home, offline=True),
        snapshot=_cpu_snapshot(),
        effective_device="cpu",
    )
    block = format_copy_block(report)
    lines = block.strip().splitlines()
    assert lines[0] == COPY_BLOCK_BEGIN
    assert lines[-1] == COPY_BLOCK_END
    keys = [line.split("=", 1)[0] for line in lines[1:-1]]
    assert keys == [
        "status",
        "os",
        "architecture",
        "python",
        "python_supported",
        "sdk_version",
        "sdk_importable",
        "configured_device",
        "effective_device",
        "gpus",
        "cache_dir",
        "offline",
        "cuda_binding",
        "optional_groups",
        "checks",
        "exit_code",
        "remediation",
    ]
    assert "status=usable" in block
    assert "optional_groups=cuda" in block
    assert "cuda:reserved" not in block
    assert "cuda_binding=no" in block
    assert "offline=true" in block
    assert "\x1b[" not in block
    assert all("\n" not in line for line in lines)


def test_home_paths_are_normalized(isolated_home: Path) -> None:
    cache = isolated_home / ".ceia-aisdk" / "nested"
    normalized = normalize_user_path(cache)
    assert normalized.startswith("~/")
    assert str(isolated_home) not in normalized
    report = build_report(
        config=_config(isolated_home, cache_dir=cache),
        snapshot=_cpu_snapshot(),
        effective_device="cpu",
    )
    assert report.cache_dir.startswith("~")
    assert str(isolated_home) not in format_copy_block(report)
    assert str(isolated_home) not in format_plain_report(report)


def test_privacy_exclusions(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER", "alice")
    monkeypatch.setenv("USERNAME", "alice")
    monkeypatch.setenv("HOSTNAME", "secret-host")
    gpu = GPUInfo(index=0, name="NVIDIA Test GPU", total_vram_mib=8192, free_vram_mib=4096)
    report = build_report(
        config=_config(isolated_home),
        snapshot=HardwareSnapshot(
            gpus=(gpu,),
            usable_gpu_indices=(0,),
            probe_status=ProbeStatus.SUCCEEDED,
            probe_detail=None,
        ),
        effective_device="cuda:0",
    )
    blob = format_plain_report(report) + format_copy_block(report)
    assert "alice" not in blob
    assert "secret-host" not in blob
    assert "GPU-aaaa" not in blob
    assert str(isolated_home) not in blob
    assert gpu.name in blob
