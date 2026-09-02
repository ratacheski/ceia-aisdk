"""Two-process concurrent pull of the same uncached alias."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import LoopbackHttpServer


@pytest.mark.enable_socket
def test_two_processes_serialize_and_leave_one_valid_file(
    tmp_path: Path,
    isolated_cache_dir: Path,
    loopback_catalog: LoopbackHttpServer,
) -> None:
    env = os.environ.copy()
    env["CEIA_AISDK_CACHE_DIR"] = str(isolated_cache_dir)
    env["CEIA_AISDK_CATALOG"] = str(tmp_path / "catalog.yaml")
    code = (
        "from ceia_aisdk import AISDKConfig\n"
        "from ceia_aisdk.registry import ensure_local\n"
        "print(ensure_local('llm/small', config=AISDKConfig.load()))\n"
    )
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", code],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    results = [proc.communicate(timeout=60) for proc in procs]
    codes = [proc.returncode for proc in procs]
    assert codes == [0, 0], results
    bin_path = isolated_cache_dir / "models" / "llm" / "small-v1.bin"
    assert bin_path.is_file()
    digest = hashlib.sha256(bin_path.read_bytes()).hexdigest()
    assert digest == loopback_catalog.fixture.sha256
    bins = list((isolated_cache_dir / "models").rglob("*.bin"))
    assert bins == [bin_path]
