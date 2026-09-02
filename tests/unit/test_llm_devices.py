"""Unit tests for LLM device selection, CUDA binding, and OOM wrapping."""

from __future__ import annotations

from pathlib import Path

import pytest

from ceia_aisdk.errors import DeviceError
from ceia_aisdk.hardware import GPUInfo, HardwareSnapshot, ProbeStatus
from ceia_aisdk.llm import LLM
from ceia_aisdk.llm.devices import resolve_generation_device
from conftest import FakeBackend


def _gpu_snapshot(free_mib: int = 8192) -> HardwareSnapshot:
    gpu = GPUInfo(index=0, name="NVIDIA Test", total_vram_mib=8192, free_vram_mib=free_mib)
    return HardwareSnapshot(
        gpus=(gpu,),
        usable_gpu_indices=(0,),
        probe_status=ProbeStatus.SUCCEEDED,
        probe_detail=None,
    )


def test_forced_cpu_ignores_visible_gpu() -> None:
    device, layers = resolve_generation_device(
        "cpu",
        snapshot=_gpu_snapshot(),
        binding_present=True,
        size_gb=0.5,
    )
    assert device == "cpu"
    assert layers == 0


def test_auto_without_binding_selects_cpu() -> None:
    device, layers = resolve_generation_device(
        "auto",
        snapshot=_gpu_snapshot(),
        binding_present=False,
        size_gb=0.5,
    )
    assert device == "cpu"
    assert layers == 0


def test_auto_with_binding_selects_cuda() -> None:
    device, layers = resolve_generation_device(
        "auto",
        snapshot=_gpu_snapshot(),
        binding_present=True,
        size_gb=0.5,
    )
    assert device == "cuda:0"
    assert layers == -1


def test_explicit_cuda_without_binding_raises() -> None:
    with pytest.raises(DeviceError) as exc_info:
        resolve_generation_device(
            "cuda",
            snapshot=_gpu_snapshot(),
            binding_present=False,
            size_gb=0.5,
        )
    assert "cpu" in exc_info.value.remediation.lower() or "llm/small" in exc_info.value.remediation


def test_explicit_cuda_without_gpu_raises() -> None:
    empty = HardwareSnapshot((), (), ProbeStatus.FAILED, "nvidia-smi was not found")
    with pytest.raises(DeviceError) as exc_info:
        resolve_generation_device("cuda", snapshot=empty, binding_present=True)
    assert "cpu" in exc_info.value.remediation.lower()


def test_oom_is_wrapped_as_device_error(fake_llm_catalog: Path, fake_backend: FakeBackend) -> None:
    del fake_llm_catalog
    fake_backend.raise_oom = True
    model = LLM(device="cpu")
    with pytest.raises(DeviceError) as exc_info:
        model.chat("hello")
    text = f"{exc_info.value} {exc_info.value.remediation}".lower()
    assert "llm/small" in text or 'device="cpu"' in text or "device=cpu" in text
    assert exc_info.value.remediation.strip()


def test_auto_vram_fallback_selects_cpu(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("WARNING")
    device, layers = resolve_generation_device(
        "auto",
        snapshot=_gpu_snapshot(free_mib=1024),
        binding_present=True,
        size_gb=4.0,
        apply_vram_fallback=True,
    )
    assert device == "cpu"
    assert layers == 0
    assert any(record.levelname == "WARNING" for record in caplog.records)


def test_auto_sufficient_vram_stays_cuda() -> None:
    device, layers = resolve_generation_device(
        "auto",
        snapshot=_gpu_snapshot(free_mib=8192),
        binding_present=True,
        size_gb=0.5,
        apply_vram_fallback=True,
    )
    assert device == "cuda:0"
    assert layers == -1


def test_explicit_cuda_does_not_fallback() -> None:
    with pytest.raises(DeviceError) as exc_info:
        resolve_generation_device(
            "cuda",
            snapshot=_gpu_snapshot(free_mib=1024),
            binding_present=True,
            size_gb=4.0,
            apply_vram_fallback=True,
        )
    assert "cpu" in exc_info.value.remediation.lower() or "llm/small" in exc_info.value.remediation
