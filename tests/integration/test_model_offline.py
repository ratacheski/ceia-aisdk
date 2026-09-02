"""Integration tests for offline cache-miss behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from ceia_aisdk import AISDKConfig
from ceia_aisdk.errors import DownloadError
from conftest import write_catalog_yaml


def test_offline_miss_does_not_open_a_socket(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_cache_dir: Path,
) -> None:
    del isolated_cache_dir
    catalog_path = tmp_path / "catalog.yaml"
    write_catalog_yaml(
        catalog_path,
        url="https://models.example.invalid/llm-small-v1.bin",
        sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        size_bytes=16777216,
    )
    monkeypatch.setenv("CEIA_AISDK_CATALOG", str(catalog_path))
    monkeypatch.setenv("CEIA_AISDK_OFFLINE", "1")
    from ceia_aisdk.registry import ensure_local

    with pytest.raises(DownloadError) as exc_info:
        ensure_local("llm/small", config=AISDKConfig.load())
    text = f"{exc_info.value} {exc_info.value.remediation}".lower()
    assert "offline" in text or "ceia_aisdk_offline" in text
    assert exc_info.value.remediation.strip()
    assert "huggingface.co" not in str(exc_info.value)
