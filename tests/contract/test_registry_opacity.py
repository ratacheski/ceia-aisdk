"""Opacity snapshots for cataloged info and public exceptions."""

from __future__ import annotations

from pathlib import Path

import pytest

from ceia_aisdk import AISDKConfig
from ceia_aisdk.errors import DownloadError
from conftest import LoopbackHttpServer, write_catalog_yaml

_FORBIDDEN = (
    "huggingface.co",
    "ceia-aisdk/llm-small-v1",
    "model.gguf",
    "Qwen/",
)


@pytest.mark.enable_socket
def test_download_error_and_info_omit_origin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_cache_dir: Path,
    loopback_http_server: LoopbackHttpServer,
) -> None:
    del isolated_cache_dir
    catalog_path = tmp_path / "catalog.yaml"
    write_catalog_yaml(
        catalog_path,
        url=loopback_http_server.artifact_url,
        sha256="0" * 64,
        size_bytes=loopback_http_server.fixture.size_bytes,
    )
    monkeypatch.setenv("CEIA_AISDK_CATALOG", str(catalog_path))
    from ceia_aisdk.registry import ensure_local, get_public_metadata

    with pytest.raises(DownloadError) as exc_info:
        ensure_local("llm/small", config=AISDKConfig.load())
    blob = f"{exc_info.value}\n{exc_info.value.remediation}"
    for token in _FORBIDDEN:
        assert token not in blob
    assert loopback_http_server.artifact_url not in blob

    meta = get_public_metadata("llm/small")
    meta_text = repr(meta)
    for token in _FORBIDDEN:
        assert token not in meta_text
    assert not hasattr(meta, "url")
