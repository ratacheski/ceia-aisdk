"""Warm-cache pull must finish quickly with zero HTTP GET requests."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from ceia_aisdk import AISDKConfig
from conftest import LoopbackHttpServer


@pytest.mark.enable_socket
def test_warm_cache_pull_is_fast_and_silent(
    isolated_cache_dir: Path,
    loopback_catalog: LoopbackHttpServer,
) -> None:
    del isolated_cache_dir
    from ceia_aisdk.registry import ensure_local

    config = AISDKConfig.load()
    ensure_local("llm/small", config=config)
    gets_after_first = loopback_catalog.gets
    start = time.perf_counter()
    ensure_local("llm/small", config=config)
    elapsed = time.perf_counter() - start
    assert elapsed <= 2.0
    assert loopback_catalog.gets == gets_after_first
