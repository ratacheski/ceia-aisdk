"""Integration tests for resumable cataloged downloads."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ceia_aisdk import AISDKConfig
from conftest import LoopbackHttpServer


@pytest.mark.enable_socket
def test_resume_after_partial_uses_range(
    isolated_cache_dir: Path,
    loopback_catalog: LoopbackHttpServer,
) -> None:
    part = isolated_cache_dir / "models" / ".tmp" / "llm-small-v1.part"
    part.parent.mkdir(parents=True, exist_ok=True)
    prefix = loopback_catalog.fixture.path.read_bytes()[: 8 * 1024 * 1024]
    part.write_bytes(prefix)
    assert len(prefix) >= 8 * 1024 * 1024

    from ceia_aisdk.registry import ensure_local

    before_range = loopback_catalog.range_gets
    destination = ensure_local("llm/small", config=AISDKConfig.load())
    assert loopback_catalog.range_gets == before_range + 1
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    assert digest == loopback_catalog.fixture.sha256
    assert not part.exists()
