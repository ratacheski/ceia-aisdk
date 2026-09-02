"""Integration tests for model list, rm, and info CLI."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from ceia_aisdk import AISDKConfig
from conftest import LoopbackHttpServer


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
def test_list_and_rm_round_trip(
    tmp_path: Path,
    isolated_cache_dir: Path,
    loopback_catalog: LoopbackHttpServer,
) -> None:
    del loopback_catalog
    from ceia_aisdk.registry import ensure_local

    ensure_local("llm/small", config=AISDKConfig.load())
    env = {
        "CEIA_AISDK_CACHE_DIR": str(isolated_cache_dir),
        "CEIA_AISDK_CATALOG": str(tmp_path / "catalog.yaml"),
    }
    listed = _run_cli(["model", "list"], env)
    assert listed.returncode == 0, listed.stderr
    assert "llm/small" in listed.stdout
    empty_before_rm = isolated_cache_dir / "models" / "llm" / "small-v1.bin"
    assert empty_before_rm.is_file()
    removed = _run_cli(["model", "rm", "llm/small"], env)
    assert removed.returncode == 0, removed.stderr
    listed_after = _run_cli(["model", "list"], env)
    assert listed_after.returncode == 0
    assert "llm/small" not in listed_after.stdout or "empty" in listed_after.stdout.lower()
    assert not empty_before_rm.exists()


@pytest.mark.enable_socket
def test_list_empty_cache_is_success(
    tmp_path: Path,
    isolated_cache_dir: Path,
    loopback_catalog: LoopbackHttpServer,
) -> None:
    del loopback_catalog
    env = {
        "CEIA_AISDK_CACHE_DIR": str(isolated_cache_dir),
        "CEIA_AISDK_CATALOG": str(tmp_path / "catalog.yaml"),
    }
    listed = _run_cli(["model", "list"], env)
    assert listed.returncode == 0, listed.stderr
    assert listed.stdout.strip()


@pytest.mark.enable_socket
def test_model_info_prints_public_fields_only(
    tmp_path: Path,
    isolated_cache_dir: Path,
    loopback_catalog: LoopbackHttpServer,
) -> None:
    del isolated_cache_dir, loopback_catalog
    env = {
        "CEIA_AISDK_CACHE_DIR": str(tmp_path / "unused-cache"),
        "CEIA_AISDK_CATALOG": str(tmp_path / "catalog.yaml"),
    }
    result = _run_cli(["model", "info", "llm/small"], env)
    assert result.returncode == 0, result.stderr
    text = result.stdout.lower()
    for field in (
        "license_family",
        "commercial_use",
        "context_length",
        "size_gb",
        "capabilities",
        "quantization_class",
    ):
        assert field in text
    assert "huggingface.co" not in result.stdout
    assert "model.gguf" not in result.stdout
    assert "sha256" not in text
    assert "http://" not in result.stdout
    assert "https://" not in result.stdout
