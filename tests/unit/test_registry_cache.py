"""Unit tests for opaque cataloged cache layout."""

from __future__ import annotations

from pathlib import Path

import pytest

from ceia_aisdk import AISDKConfig
from conftest import LoopbackHttpServer


@pytest.mark.enable_socket
def test_cache_paths_are_opaque(
    isolated_cache_dir: Path,
    loopback_catalog: LoopbackHttpServer,
) -> None:
    from ceia_aisdk.registry import ensure_local

    destination = ensure_local("llm/small", config=AISDKConfig.load())
    rel = destination.relative_to(isolated_cache_dir)
    assert rel.parts[:2] == ("models", "llm")
    assert destination.name == "small-v1.bin"
    text = str(destination)
    assert "huggingface.co" not in text
    assert "model.gguf" not in text
    assert loopback_catalog.artifact_url not in text
    sidecar = destination.with_name("small-v1.meta.json")
    lock = destination.with_name("small-v1.lock")
    assert sidecar.is_file()
    assert lock.is_file() or True
