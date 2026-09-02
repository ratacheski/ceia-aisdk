"""Offline cache-miss failures must complete within 100 ms."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from ceia_aisdk import AISDKConfig
from ceia_aisdk.errors import DownloadError
from conftest import write_catalog_yaml


def test_offline_miss_completes_within_100ms(
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

    config = AISDKConfig.load()
    start = time.perf_counter()
    with pytest.raises(DownloadError):
        ensure_local("llm/small", config=config)
    elapsed = time.perf_counter() - start
    assert elapsed <= 0.100
