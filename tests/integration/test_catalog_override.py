"""Integration tests for CEIA_AISDK_CATALOG overrides."""

from __future__ import annotations

import http.server
import threading
from pathlib import Path

import pytest
import yaml

from ceia_aisdk.errors import DownloadError
from ceia_aisdk.registry.catalog import load_catalog
from conftest import write_catalog_yaml


def test_local_override_replaces_bundled_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    write_catalog_yaml(
        catalog_path,
        url="https://models.example.invalid/llm-small-v1.bin",
        sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        size_bytes=16777216,
    )
    monkeypatch.setenv("CEIA_AISDK_CATALOG", str(catalog_path))
    catalog = load_catalog()
    assert catalog.pin("llm", "small").versions[1].url.endswith("llm-small-v1.bin")
    with pytest.raises(KeyError):
        catalog.pin("llm", "medium")


def test_unset_override_uses_bundled_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CEIA_AISDK_CATALOG", raising=False)
    catalog = load_catalog()
    catalog.pin("llm", "medium")
    catalog.pin("llm", "large")


def test_invalid_override_schema_names_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_path = tmp_path / "bad.yaml"
    catalog_path.write_text("schema_version: 9\nmodels: {}\n", encoding="utf-8")
    monkeypatch.setenv("CEIA_AISDK_CATALOG", str(catalog_path))
    with pytest.raises(DownloadError) as exc_info:
        load_catalog()
    assert "schema" in exc_info.value.remediation.lower()


@pytest.mark.enable_socket
def test_http_override_uses_only_that_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    socket_enabled: object,
) -> None:
    del socket_enabled
    document = {
        "schema_version": 1,
        "essentials": ["llm/small"],
        "models": {
            "llm": {
                "small": {
                    "latest": 1,
                    "versions": {
                        1: {
                            "url": "https://models.example.invalid/override.bin",
                            "sha256": (
                                "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
                            ),
                            "size_bytes": 16,
                            "public": {
                                "license_family": "apache-2.0",
                                "commercial_use": True,
                                "context_length": 8,
                                "size_gb": 0.01,
                                "capabilities": ["chat"],
                                "quantization_class": "compact",
                            },
                        }
                    },
                }
            }
        },
    }
    payload = yaml.safe_dump(document, sort_keys=False).encode("utf-8")

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            del format, args

        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/yaml")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        monkeypatch.setenv("CEIA_AISDK_CATALOG", f"http://{host}:{port}/catalog.yaml")
        catalog = load_catalog()
        assert catalog.pin("llm", "small").versions[1].url.endswith("override.bin")
        with pytest.raises(KeyError):
            catalog.pin("llm", "medium")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
