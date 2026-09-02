"""Integration tests for cataloged pull, checksum promotion, and where."""

from __future__ import annotations

import hashlib
import json
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
def test_ensure_local_promotes_checksum_and_where(
    tmp_path: Path,
    isolated_cache_dir: Path,
    loopback_catalog: LoopbackHttpServer,
) -> None:
    from ceia_aisdk import AISDKConfig
    from ceia_aisdk.registry import ensure_local

    config = AISDKConfig.load()
    destination = ensure_local("llm/small", config=config)
    expected = isolated_cache_dir / "models" / "llm" / "small-v1.bin"
    assert destination == expected
    assert destination.is_file()
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    assert digest == loopback_catalog.fixture.sha256
    sidecar = expected.with_name("small-v1.meta.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["source"] == "catalog"
    assert payload["sha256"] == loopback_catalog.fixture.sha256
    assert "huggingface.co" not in str(destination)

    env = {
        "CEIA_AISDK_CACHE_DIR": str(isolated_cache_dir),
        "CEIA_AISDK_CATALOG": str(tmp_path / "catalog.yaml"),
    }
    where = _run_cli(["model", "where", "llm/small"], env)
    assert where.returncode == 0, where.stderr
    assert Path(where.stdout.strip()) == expected


@pytest.mark.enable_socket
def test_cli_pull_writes_opaque_cache(
    tmp_path: Path,
    isolated_cache_dir: Path,
    loopback_catalog: LoopbackHttpServer,
) -> None:
    del loopback_catalog
    env = {
        "CEIA_AISDK_CACHE_DIR": str(isolated_cache_dir),
        "CEIA_AISDK_CATALOG": str(tmp_path / "catalog.yaml"),
    }
    result = _run_cli(["model", "pull", "llm/small"], env)
    assert result.returncode == 0, result.stderr
    bin_path = isolated_cache_dir / "models" / "llm" / "small-v1.bin"
    assert bin_path.is_file()
    assert "huggingface.co" not in result.stdout
    assert "huggingface.co" not in result.stderr


@pytest.mark.enable_socket
def test_checksum_mismatch_is_not_promoted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_cache_dir: Path,
    loopback_http_server: LoopbackHttpServer,
) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    write_catalog_yaml(
        catalog_path,
        url=loopback_http_server.artifact_url,
        sha256="0" * 64,
        size_bytes=loopback_http_server.fixture.size_bytes,
    )
    monkeypatch.setenv("CEIA_AISDK_CATALOG", str(catalog_path))
    from ceia_aisdk import AISDKConfig
    from ceia_aisdk.errors import DownloadError
    from ceia_aisdk.registry import ensure_local

    with pytest.raises(DownloadError) as exc_info:
        ensure_local("llm/small", config=AISDKConfig.load())
    assert exc_info.value.remediation.strip()
    assert "huggingface.co" not in str(exc_info.value)
    expected = isolated_cache_dir / "models" / "llm" / "small-v1.bin"
    assert not expected.exists()


@pytest.mark.enable_socket
def test_tamper_fails_verify_and_is_not_promoted(
    tmp_path: Path,
    isolated_cache_dir: Path,
    loopback_catalog: LoopbackHttpServer,
) -> None:
    del loopback_catalog
    from ceia_aisdk import AISDKConfig
    from ceia_aisdk.registry import ensure_local

    destination = ensure_local("llm/small", config=AISDKConfig.load())
    data = bytearray(destination.read_bytes())
    data[0] ^= 0xFF
    destination.write_bytes(data)
    env = {
        "CEIA_AISDK_CACHE_DIR": str(isolated_cache_dir),
        "CEIA_AISDK_CATALOG": str(tmp_path / "catalog.yaml"),
    }
    verify = _run_cli(["model", "verify"], env)
    assert verify.returncode == 1
    assert destination.is_file()


@pytest.mark.enable_socket
def test_pull_ignores_commercial_use_false(
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
        commercial_use=False,
    )
    monkeypatch.setenv("CEIA_AISDK_CATALOG", str(catalog_path))
    from ceia_aisdk import AISDKConfig
    from ceia_aisdk.registry import ensure_local

    destination = ensure_local("llm/small", config=AISDKConfig.load())
    assert destination.is_file()
    assert (isolated_cache_dir / "models" / "llm" / "small-v1.bin").is_file()
