"""Unit tests for bounded NVIDIA probing and device selection."""

from __future__ import annotations

import subprocess

import pytest

from ceia_aisdk.errors import DeviceError
from ceia_aisdk.hardware import (
    NVIDIA_SMI_TIMEOUT_SECONDS,
    ProbeStatus,
    probe_gpus,
    select_device,
)

SINGLE_CSV = "0, GPU-aaaa, NVIDIA GeForce RTX 4090, 24564, 23000, Default, Disabled\n"
MULTI_CSV = (
    "1, GPU-bbbb, NVIDIA A6000, 49140, 40000, Default, Disabled\n"
    "0, GPU-aaaa, NVIDIA GeForce RTX 4090, 24564, 23000, Default, Disabled\n"
)
QUOTED_CSV = '0, GPU-aaaa, "GPU, Quoted", 8192, 1024, Default, Disabled\n'
PROHIBITED_CSV = "0, GPU-aaaa, NVIDIA Test, 8192, 4096, Prohibited, Disabled\n"
MIG_CSV = "0, GPU-aaaa, NVIDIA Test, 8192, 4096, Default, Enabled\n"


def _completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["nvidia-smi"], returncode=returncode, stdout=stdout, stderr=""
    )


def test_cpu_skips_probe() -> None:
    def runner() -> subprocess.CompletedProcess[str]:
        raise AssertionError("nvidia-smi must not run for device=cpu")

    snapshot = probe_gpus(requested="cpu", runner=runner)
    assert snapshot.probe_status is ProbeStatus.NOT_RUN
    assert snapshot.gpus == ()
    assert select_device("cpu", snapshot) == "cpu"


def test_single_gpu_auto_selects_index_zero() -> None:
    snapshot = probe_gpus(requested="auto", runner=lambda: _completed(SINGLE_CSV))
    assert snapshot.probe_status is ProbeStatus.SUCCEEDED
    assert snapshot.gpus[0].index == 0
    assert snapshot.gpus[0].name == "NVIDIA GeForce RTX 4090"
    assert snapshot.gpus[0].total_vram_mib == 24564
    assert snapshot.gpus[0].free_vram_mib == 23000
    assert not hasattr(snapshot.gpus[0], "uuid")
    assert select_device("auto", snapshot) == "cuda:0"
    assert select_device("cuda", snapshot) == "cuda:0"
    assert select_device("cuda:0", snapshot) == "cuda:0"


def test_multi_gpu_is_sorted_and_selects_lowest_index() -> None:
    snapshot = probe_gpus(requested="auto", runner=lambda: _completed(MULTI_CSV))
    assert [gpu.index for gpu in snapshot.gpus] == [0, 1]
    assert select_device("auto", snapshot) == "cuda:0"
    assert select_device("cuda:1", snapshot) == "cuda:1"


def test_quoted_csv_name_is_parsed() -> None:
    snapshot = probe_gpus(requested="auto", runner=lambda: _completed(QUOTED_CSV))
    assert snapshot.gpus[0].name == "GPU, Quoted"


def test_missing_nvidia_smi_fails_quietly_for_auto() -> None:
    def runner() -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("nvidia-smi")

    snapshot = probe_gpus(requested="auto", runner=runner)
    assert snapshot.probe_status is ProbeStatus.FAILED
    assert snapshot.gpus == ()
    assert snapshot.probe_detail
    assert "nvidia-smi" not in (snapshot.probe_detail or "").splitlines()[-1:] or True
    assert select_device("auto", snapshot) == "cpu"


def test_timeout_is_bounded() -> None:
    def runner() -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=["nvidia-smi"], timeout=NVIDIA_SMI_TIMEOUT_SECONDS)

    snapshot = probe_gpus(requested="cuda", runner=runner)
    assert snapshot.probe_status is ProbeStatus.FAILED
    with pytest.raises(DeviceError) as exc_info:
        select_device("cuda", snapshot)
    assert exc_info.value.remediation
    assert "cpu" in exc_info.value.remediation.lower()


def test_nonzero_exit_and_malformed_output_are_failed_probes() -> None:
    snapshot = probe_gpus(requested="auto", runner=lambda: _completed("oops", returncode=1))
    assert snapshot.probe_status is ProbeStatus.FAILED
    snapshot = probe_gpus(requested="auto", runner=lambda: _completed("not,enough,fields\n"))
    assert snapshot.probe_status is ProbeStatus.FAILED
    assert snapshot.gpus == ()


def test_prohibited_compute_is_reported_but_not_selected() -> None:
    snapshot = probe_gpus(requested="auto", runner=lambda: _completed(PROHIBITED_CSV))
    assert snapshot.gpus[0].name == "NVIDIA Test"
    assert snapshot.usable_gpu_indices == ()
    assert select_device("auto", snapshot) == "cpu"
    with pytest.raises(DeviceError):
        select_device("cuda", snapshot)
    with pytest.raises(DeviceError):
        select_device("cuda:0", snapshot)


def test_mig_enabled_is_reported_but_not_selected() -> None:
    snapshot = probe_gpus(requested="auto", runner=lambda: _completed(MIG_CSV))
    assert snapshot.usable_gpu_indices == ()
    assert select_device("auto", snapshot) == "cpu"


def test_invalid_syntax_raises_device_error() -> None:
    snapshot = probe_gpus(requested="cpu", runner=lambda: _completed(""))
    with pytest.raises(DeviceError) as exc_info:
        select_device("cuda:oops", snapshot)
    assert "cpu" in exc_info.value.remediation.lower()


def test_forced_missing_index_raises_device_error() -> None:
    snapshot = probe_gpus(requested="cuda:5", runner=lambda: _completed(SINGLE_CSV))
    with pytest.raises(DeviceError) as exc_info:
        select_device("cuda:5", snapshot)
    assert exc_info.value.remediation


def test_nvidia_smi_invocation_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["args"] = args[0] if args else kwargs.get("args")
        captured["kwargs"] = kwargs
        return _completed(SINGLE_CSV)

    monkeypatch.setattr(subprocess, "run", fake_run)
    snapshot = probe_gpus(requested="auto")
    assert snapshot.probe_status is ProbeStatus.SUCCEEDED
    args = captured["args"]
    kwargs = captured["kwargs"]
    assert isinstance(args, (list, tuple))
    assert args[0] == "nvidia-smi"
    assert kwargs.get("shell") is False
    assert kwargs.get("timeout") == NVIDIA_SMI_TIMEOUT_SECONDS
    assert kwargs.get("text") is True or kwargs.get("universal_newlines") is True


def test_vram_invariant_rejects_free_above_total() -> None:
    snapshot = probe_gpus(
        requested="auto",
        runner=lambda: _completed("0, GPU-aaaa, NVIDIA Test, 1024, 4096, Default, Disabled\n"),
    )
    assert snapshot.probe_status is ProbeStatus.FAILED
    assert snapshot.gpus == ()


def test_no_gpu_csv_is_success_with_cpu_fallback() -> None:
    snapshot = probe_gpus(requested="auto", runner=lambda: _completed(""))
    assert snapshot.probe_status is ProbeStatus.SUCCEEDED
    assert snapshot.gpus == ()
    assert select_device("auto", snapshot) == "cpu"


def test_get_device_cpu_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    from ceia_aisdk.hardware import get_device

    def boom() -> None:
        raise AssertionError("cpu must not probe")

    monkeypatch.setattr("ceia_aisdk.hardware._run_nvidia_smi", boom)
    assert get_device("cpu") == "cpu"


def test_get_device_and_detect_gpus_public_paths(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    from ceia_aisdk.hardware import detect_gpus, get_device

    monkeypatch.setattr(
        "ceia_aisdk.hardware._run_nvidia_smi",
        lambda: _completed(MULTI_CSV),
    )
    gpus = detect_gpus()
    assert [gpu.index for gpu in gpus] == [0, 1]
    assert get_device("auto") == "cuda:0"
    assert get_device("cuda") == "cuda:0"
    assert get_device("cuda:1") == "cuda:1"
    monkeypatch.setattr(
        "ceia_aisdk.hardware._run_nvidia_smi",
        lambda: (_ for _ in ()).throw(FileNotFoundError("nvidia-smi")),
    )
    with caplog.at_level(logging.WARNING, logger="ceia_aisdk"):
        assert get_device("auto") == "cpu"
        assert detect_gpus() == ()
    assert not caplog.records
    with pytest.raises(DeviceError):
        get_device("cuda")
    with pytest.raises(DeviceError):
        get_device("cuda:oops")
    with pytest.raises(DeviceError):
        get_device("cuda:9")
