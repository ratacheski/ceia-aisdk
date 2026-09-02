"""Integration tests for model pull --essentials."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from conftest import LoopbackHttpServer, write_catalog_yaml


def _run_cli(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(
        ["ceia-aisdk", *args],
        capture_output=True,
        text=True,
        env=merged,
        check=False,
    )


@pytest.mark.enable_socket
def test_essentials_pulls_present_alias(
    tmp_path: Path,
    isolated_cache_dir: Path,
    loopback_catalog: LoopbackHttpServer,
) -> None:
    del loopback_catalog
    env = {
        "CEIA_AISDK_CACHE_DIR": str(isolated_cache_dir),
        "CEIA_AISDK_CATALOG": str(tmp_path / "catalog.yaml"),
    }
    result = _run_cli(["model", "pull", "--essentials"], env)
    assert result.returncode == 0, result.stderr
    assert (isolated_cache_dir / "models" / "llm" / "small-v1.bin").is_file()
    dist = Path("dist")
    if dist.exists():
        assert not any(isolated_cache_dir.rglob("*.whl"))


@pytest.mark.enable_socket
def test_missing_essential_warns_without_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_cache_dir: Path,
    loopback_http_server: LoopbackHttpServer,
) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    write_catalog_yaml(
        catalog_path,
        url=loopback_http_server.artifact_url,
        sha256=loopback_http_server.fixture.sha256,
        size_bytes=loopback_http_server.fixture.size_bytes,
        essentials=["llm/small", "voice/missing"],
    )
    monkeypatch.setenv("CEIA_AISDK_CATALOG", str(catalog_path))
    env = {
        "CEIA_AISDK_CACHE_DIR": str(isolated_cache_dir),
        "CEIA_AISDK_CATALOG": str(catalog_path),
    }
    result = _run_cli(["model", "pull", "--essentials"], env)
    assert result.returncode == 0, result.stderr
    assert "warning" in result.stderr.lower()
    assert "voice/missing" in result.stderr
    assert (isolated_cache_dir / "models" / "llm" / "small-v1.bin").is_file()
