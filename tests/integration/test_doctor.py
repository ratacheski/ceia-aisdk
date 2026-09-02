"""Integration tests for the installed doctor command."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ceia_aisdk.cli import app

pytestmark = pytest.mark.allow_llama_cpp

runner = CliRunner()
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
COPY_BEGIN = "--- CEIA AI SDK doctor: copy this ---"
COPY_END = "--- end CEIA AI SDK doctor ---"
SECRET = "s3cret-token-should-never-leak"


def _env(isolated_home: Path, extra: Mapping[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(isolated_home)
    env["CEIA_AISDK_DEVICE"] = extra.get("CEIA_AISDK_DEVICE", "cpu") if extra else "cpu"
    if extra:
        env.update(extra)
    return env


def _fake_nvidia_smi(
    tmp_path: Path, output: str, *, sleep: float = 0.0, returncode: int = 0
) -> Path:
    script = tmp_path / "nvidia-smi"
    body = "\n".join(
        [
            "#!/usr/bin/env python3",
            "import sys, time",
            f"time.sleep({sleep!r})",
            f"sys.stdout.write({output!r})",
            f"raise SystemExit({returncode})",
        ]
    )
    script.write_text(body, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def test_cpu_doctor_exit_zero_and_copy_block(isolated_home: Path) -> None:
    result = runner.invoke(app, ["doctor"], env=_env(isolated_home))
    assert result.exit_code == 0, result.output
    assert COPY_BEGIN in result.stdout
    assert COPY_END in result.stdout
    assert "configured_device=cpu" in result.stdout
    assert "effective_device=cpu" in result.stdout
    assert "optional_groups=cuda" in result.stdout
    assert "cuda:reserved" not in result.stdout
    assert "cuda_binding=" in result.stdout
    assert ANSI_RE.search(result.stdout) is None


def test_redirected_output_has_no_ansi(isolated_home: Path) -> None:
    result = runner.invoke(
        app, ["doctor"], env=_env(isolated_home, {"TERM": "dumb", "NO_COLOR": "1"})
    )
    assert result.exit_code == 0
    assert ANSI_RE.search(result.stdout) is None
    assert ANSI_RE.search(result.stderr or "") is None


def test_forced_cuda_without_gpu_exits_one(isolated_home: Path, tmp_path: Path) -> None:
    smi = _fake_nvidia_smi(tmp_path, "", returncode=127)
    env = _env(
        isolated_home, {"CEIA_AISDK_DEVICE": "cuda", "PATH": f"{smi.parent}:{os.environ['PATH']}"}
    )
    result = runner.invoke(app, ["doctor"], env=env)
    assert result.exit_code == 1, result.output
    assert "status=unusable" in result.stdout
    assert "cpu" in result.stdout.lower()
    assert "Traceback" not in result.stdout
    assert "Traceback" not in (result.stderr or "")


def test_mocked_gpu_doctor_lists_index_and_memory(isolated_home: Path, tmp_path: Path) -> None:
    csv = "0, GPU-secret-uuid, NVIDIA GeForce RTX 4090, 24564, 23000, Default, Disabled\n"
    smi = _fake_nvidia_smi(tmp_path, csv)
    env = _env(
        isolated_home, {"CEIA_AISDK_DEVICE": "auto", "PATH": f"{smi.parent}:{os.environ['PATH']}"}
    )
    result = runner.invoke(app, ["doctor"], env=env)
    assert result.exit_code == 0, result.output
    assert "NVIDIA GeForce RTX 4090" in result.stdout
    assert "24564" in result.stdout
    assert "23000" in result.stdout
    assert "GPU-secret-uuid" not in result.stdout
    assert "effective_device=cuda:0" in result.stdout


def test_privacy_and_config_errors(isolated_home: Path) -> None:
    config_dir = isolated_home / ".ceia-aisdk"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        f'[core\ndevice = "cpu"\npassword = "{SECRET}"\n',
        encoding="utf-8",
    )
    env = _env(isolated_home, {"USER": "alice", "HOSTNAME": "secret-host"})
    result = runner.invoke(app, ["doctor"], env=env)
    assert result.exit_code == 1
    blob = result.stdout + (result.stderr or "")
    assert SECRET not in blob
    assert "alice" not in blob
    assert "secret-host" not in blob
    assert "Traceback" not in blob
    assert COPY_BEGIN in result.stdout


def test_installed_entrypoint_cpu(isolated_home: Path) -> None:
    command = shutil.which("ceia-aisdk")
    assert command
    result = subprocess.run(
        [command, "doctor"],
        check=False,
        capture_output=True,
        text=True,
        env=_env(isolated_home),
    )
    assert result.returncode == 0, result.stderr
    assert COPY_BEGIN in result.stdout
    assert ANSI_RE.search(result.stdout) is None


def test_invalid_environment_and_forced_cuda_show_remediation(
    isolated_home: Path, tmp_path: Path
) -> None:
    invalid_env = _env(isolated_home, {"CEIA_AISDK_DEVICE": "not-a-device"})
    invalid = runner.invoke(app, ["doctor"], env=invalid_env)
    assert invalid.exit_code == 1
    invalid_blob = invalid.stdout + (invalid.stderr or "")
    assert "Traceback" not in invalid_blob
    assert "not-a-device" not in invalid_blob or "device" in invalid_blob.lower()
    assert "remediation" in invalid_blob.lower() or "auto, cpu, cuda" in invalid_blob.lower()
    smi = _fake_nvidia_smi(tmp_path, "")
    cuda_env = _env(
        isolated_home,
        {
            "CEIA_AISDK_DEVICE": "cuda",
            "PATH": f"{smi.parent}:{os.environ['PATH']}",
        },
    )
    cuda = runner.invoke(app, ["doctor"], env=cuda_env)
    assert cuda.exit_code == 1
    cuda_blob = cuda.stdout + (cuda.stderr or "")
    assert "Traceback" not in cuda_blob
    assert "cpu" in cuda_blob.lower()
    assert COPY_BEGIN in cuda.stdout
