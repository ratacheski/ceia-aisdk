"""Integration tests for path and hf:// catalog bypasses."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ceia_aisdk import AISDKConfig
from ceia_aisdk.errors import DownloadError
from conftest import LoopbackHttpServer, ModelFixture


def test_local_path_bypass_stores_custom_source(
    tmp_path: Path,
    isolated_cache_dir: Path,
    model_fixture: ModelFixture,
) -> None:
    from ceia_aisdk.registry import ensure_local

    source = tmp_path / "custom-weight.bin"
    source.write_bytes(model_fixture.path.read_bytes()[: 1024 * 1024])
    destination = ensure_local(str(source), config=AISDKConfig.load())
    assert destination.parent.name == "custom"
    assert destination.name == "custom-weight.bin"
    sidecar = destination.with_name("custom-weight.bin.meta.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["source"] == "bypass"
    cataloged = isolated_cache_dir / "models" / "llm" / "small-v1.bin"
    assert not cataloged.exists()


@pytest.mark.enable_socket
def test_hf_bypass_stores_custom_without_rewriting_catalog_names(
    isolated_cache_dir: Path,
    loopback_catalog: LoopbackHttpServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ceia_aisdk.registry import cache as cache_mod
    from ceia_aisdk.registry import ensure_local

    monkeypatch.setattr(cache_mod, "_hf_url", lambda token: loopback_catalog.artifact_url)
    destination = ensure_local("hf://org/demo/weights.bin", config=AISDKConfig.load())
    assert destination.parent.name == "custom"
    assert destination.name == "weights.bin"
    sidecar = destination.with_name("weights.bin.meta.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["source"] == "bypass"
    assert not (isolated_cache_dir / "models" / "llm" / "small-v1.bin").exists()


def test_missing_local_path_is_download_error(isolated_cache_dir: Path) -> None:
    del isolated_cache_dir
    from ceia_aisdk.registry import ensure_local

    with pytest.raises(DownloadError):
        ensure_local("/no/such/model.bin", config=AISDKConfig.load())
