"""Integration tests for offline LLM cache misses."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from ceia_aisdk.errors import DownloadError
from ceia_aisdk.llm import LLM
from conftest import write_catalog_yaml


def test_offline_cache_miss_raises_download_error_quickly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_cache_dir: Path,
    isolated_home: Path,
) -> None:
    del isolated_home
    catalog_path = tmp_path / "offline-catalog.yaml"
    write_catalog_yaml(
        catalog_path,
        url="https://example.invalid/missing.gguf",
        sha256="0" * 64,
        size_bytes=16,
    )
    monkeypatch.setenv("CEIA_AISDK_CATALOG", str(catalog_path))
    monkeypatch.setenv("CEIA_AISDK_OFFLINE", "1")
    monkeypatch.setenv("CEIA_AISDK_DEVICE", "cpu")
    start = time.perf_counter()
    with pytest.raises(DownloadError) as exc_info:
        LLM(device="cpu")
    elapsed = time.perf_counter() - start
    assert elapsed <= 1.0
    assert exc_info.value.remediation.strip()
    assert isolated_cache_dir.is_dir()


def test_offline_cache_miss_does_not_import_llama_cpp(tmp_path: Path) -> None:
    catalog_path = tmp_path / "offline-catalog.yaml"
    write_catalog_yaml(
        catalog_path,
        url="https://example.invalid/missing.gguf",
        sha256="0" * 64,
        size_bytes=16,
    )
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    code = f"""
import os, sys, time
os.environ['HOME'] = {str(home)!r}
os.environ['CEIA_AISDK_CATALOG'] = {str(catalog_path)!r}
os.environ['CEIA_AISDK_CACHE_DIR'] = {str(cache_dir)!r}
os.environ['CEIA_AISDK_OFFLINE'] = '1'
os.environ['CEIA_AISDK_DEVICE'] = 'cpu'
from ceia_aisdk.errors import DownloadError
from ceia_aisdk.llm import LLM
assert 'llama_cpp' not in sys.modules
start = time.perf_counter()
try:
    LLM(device='cpu')
except DownloadError:
    pass
else:
    raise SystemExit('expected DownloadError')
assert time.perf_counter() - start <= 1.0
assert 'llama_cpp' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr + result.stdout
