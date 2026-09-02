"""Timing and network isolation tests for doctor."""

from __future__ import annotations

import os
import shutil
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from ceia_aisdk.hardware import NVIDIA_SMI_TIMEOUT_SECONDS

_DOCTOR_LIMIT_SECONDS = 5.0


def _cpu_env(isolated_home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(isolated_home)
    env["CEIA_AISDK_DEVICE"] = "cpu"
    return env


def test_cpu_doctor_completes_within_five_seconds(isolated_home: Path) -> None:
    command = shutil.which("ceia-aisdk")
    assert command
    start = time.perf_counter()
    result = subprocess.run(
        [command, "doctor"],
        check=False,
        capture_output=True,
        text=True,
        env=_cpu_env(isolated_home),
        timeout=_DOCTOR_LIMIT_SECONDS + 1,
    )
    elapsed = time.perf_counter() - start
    assert result.returncode == 0, result.stderr
    assert elapsed <= _DOCTOR_LIMIT_SECONDS


def test_probe_timeout_is_two_seconds(isolated_home: Path, tmp_path: Path) -> None:
    script = tmp_path / "nvidia-smi"
    script.write_text("#!/bin/sh\nsleep 8\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    env = _cpu_env(isolated_home)
    env["CEIA_AISDK_DEVICE"] = "auto"
    env["PATH"] = f"{script.parent}:{env.get('PATH', '')}"
    start = time.perf_counter()
    result = subprocess.run(
        ["ceia-aisdk", "doctor"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=NVIDIA_SMI_TIMEOUT_SECONDS + 3,
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 6
    assert result.returncode in {0, 1}


def test_doctor_makes_zero_network_attempts(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from ceia_aisdk.cli import app

    def blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network attempt during doctor")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    result = CliRunner().invoke(app, ["doctor"], env=_cpu_env(isolated_home))
    assert result.exit_code == 0, result.output


def test_doctor_does_not_import_inference_backends(isolated_home: Path) -> None:
    code = """
import sys
from typer.testing import CliRunner
from ceia_aisdk.cli import app
result = CliRunner().invoke(app, ["doctor"])
forbidden = ["torch", "llama_cpp", "faster_whisper", "piper"]
loaded = [name for name in forbidden if name in sys.modules]
raise SystemExit(0 if result.exit_code in {0, 1} and not loaded else 1)
"""
    env = _cpu_env(isolated_home)
    result = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True, env=env
    )
    assert result.returncode == 0, result.stderr
