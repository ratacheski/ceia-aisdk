"""Shared isolated-home, environment, socket, import, and model-fixture helpers."""

from __future__ import annotations

import hashlib
import http.server
import os
import sys
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

FORBIDDEN_BACKENDS = (
    "torch",
    "llama_cpp",
    "faster_whisper",
    "piper",
)

_ENV_PREFIX = "CEIA_AISDK_"
_FIXTURE_SIZE_BYTES = 16 * 1024 * 1024
enable_socket = pytest.mark.enable_socket


@dataclass
class ModelFixture:
    """Generated cataloged artifact used by loopback download tests."""

    path: Path
    sha256: str
    size_bytes: int


@dataclass
class LoopbackHttpServer:
    """Loopback HTTP server that serves the model fixture with Range support."""

    base_url: str
    artifact_url: str
    fixture: ModelFixture
    request_count: list[int] = field(default_factory=lambda: [0])
    range_count: list[int] = field(default_factory=lambda: [0])

    @property
    def gets(self) -> int:
        """Return the number of GET requests received."""
        return self.request_count[0]

    @property
    def range_gets(self) -> int:
        """Return the number of GET requests that included a Range header."""
        return self.range_count[0]


def pytest_configure(config: pytest.Config) -> None:
    """Register the loopback socket marker used by download tests.

    Args:
        config: Pytest configuration object.
    """
    config.addinivalue_line(
        "markers",
        "enable_socket: allow network sockets for loopback HTTP fixture tests",
    )


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a temporary home directory and point HOME at it.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        The created home directory. The SDK cache and configuration
        directories are not created.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return home


@pytest.fixture
def isolated_cache_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clean_ceia_environment: None,
) -> Path:
    """Return an isolated cache directory and point CEIA_AISDK_CACHE_DIR at it.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.
        clean_ceia_environment: Autouse fixture that clears CEIA_AISDK_* first.

    Returns:
        The created cache directory. Model files are not created.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setenv("CEIA_AISDK_CACHE_DIR", str(cache_dir))
    return cache_dir


@pytest.fixture(autouse=True)
def clean_ceia_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove CEIA_AISDK_* variables so tests start from a clean process.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """
    for key in list(os.environ):
        if key.startswith(_ENV_PREFIX):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def socket_blocking() -> None:
    """Keep network sockets disabled for every test.

    pytest-socket is enabled through ``--disable-socket`` in pyproject.toml.
    Loopback download tests opt in with ``@pytest.mark.enable_socket`` or by
    requesting ``loopback_http_server``.
    """


@pytest.fixture(autouse=True)
def assert_no_backend_imports() -> Iterator[None]:
    """Fail if a test loads a forbidden inference backend.

    Yields:
        Control to the test body, then asserts that no forbidden module
        was imported.
    """
    before = {name for name in sys.modules if _is_forbidden_backend(name)}
    yield
    after = {name for name in sys.modules if _is_forbidden_backend(name)}
    newly_loaded = sorted(after - before)
    assert not newly_loaded, f"Forbidden inference backends were imported: {newly_loaded}"


@pytest.fixture(scope="session")
def model_fixture(tmp_path_factory: pytest.TempPathFactory) -> ModelFixture:
    """Generate a deterministic fixture of at least 16 MiB with a known SHA-256.

    Args:
        tmp_path_factory: Session-scoped temporary directory factory.

    Returns:
        Fixture path, checksum, and size.
    """
    path = tmp_path_factory.mktemp("model-fixture") / "artifact.bin"
    digest = hashlib.sha256()
    with path.open("wb") as handle:
        remaining = _FIXTURE_SIZE_BYTES
        block = bytes(range(256)) * 64  # 16 KiB repeating pattern
        while remaining > 0:
            chunk = block if remaining >= len(block) else block[:remaining]
            handle.write(chunk)
            digest.update(chunk)
            remaining -= len(chunk)
    return ModelFixture(path=path, sha256=digest.hexdigest(), size_bytes=_FIXTURE_SIZE_BYTES)


@pytest.fixture
def loopback_http_server(
    model_fixture: ModelFixture,
    socket_enabled: Any,
) -> Iterator[LoopbackHttpServer]:
    """Serve the model fixture on loopback with Range support and request counts.

    Args:
        model_fixture: Generated artifact to serve.
        socket_enabled: pytest-socket fixture that re-enables sockets.

    Yields:
        Server metadata including the artifact URL and request counters.
    """
    del socket_enabled
    payload = model_fixture.path.read_bytes()
    request_count = [0]
    range_count = [0]

    class _RangeHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            del format, args

        def do_GET(self) -> None:  # noqa: N802
            request_count[0] += 1
            range_header = self.headers.get("Range")
            start = 0
            end = len(payload) - 1
            status = 200
            if range_header:
                range_count[0] += 1
                status = 206
                start, end = _parse_byte_range(range_header, len(payload))
            body = payload[start : end + 1]
            self.send_response(status)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            if status == 206:
                self.send_header(
                    "Content-Range",
                    f"bytes {start}-{end}/{len(payload)}",
                )
            self.end_headers()
            self.wfile.write(body)

        def do_HEAD(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _RangeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    base_url = f"http://{host}:{port}"
    try:
        yield LoopbackHttpServer(
            base_url=base_url,
            artifact_url=f"{base_url}/artifact.bin",
            fixture=model_fixture,
            request_count=request_count,
            range_count=range_count,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def loopback_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    loopback_http_server: LoopbackHttpServer,
    isolated_cache_dir: Path,
) -> LoopbackHttpServer:
    """Point the process at a local catalog that serves the loopback fixture.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.
        loopback_http_server: Range-capable fixture server.
        isolated_cache_dir: Isolated cache directory.

    Returns:
        The loopback server. ``CEIA_AISDK_CATALOG`` is set for the test.
    """
    del isolated_cache_dir
    catalog_path = tmp_path / "catalog.yaml"
    write_catalog_yaml(
        catalog_path,
        url=loopback_http_server.artifact_url,
        sha256=loopback_http_server.fixture.sha256,
        size_bytes=loopback_http_server.fixture.size_bytes,
    )
    monkeypatch.setenv("CEIA_AISDK_CATALOG", str(catalog_path))
    return loopback_http_server


def write_catalog_yaml(
    path: Path,
    *,
    url: str,
    sha256: str,
    size_bytes: int,
    latest: int = 1,
    essentials: list[str] | None = None,
    commercial_use: bool = True,
    extra_models: dict[str, Any] | None = None,
) -> Path:
    """Write a schema_version 1 catalog that pins ``llm/small`` to a fixture URL.

    Args:
        path: Destination YAML path.
        url: Single download URL for ``llm/small@1``.
        sha256: Lowercase hex checksum.
        size_bytes: Declared artifact size.
        latest: Latest pin for ``llm/small``.
        essentials: Essential aliases, or ``[llm/small]`` when omitted.
        commercial_use: Public commercial-use flag.
        extra_models: Optional extra domain mapping merged into ``models``.

    Returns:
        The written path.
    """
    import yaml

    document: dict[str, Any] = {
        "schema_version": 1,
        "essentials": essentials if essentials is not None else ["llm/small"],
        "models": {
            "llm": {
                "small": {
                    "latest": latest,
                    "versions": {
                        1: {
                            "url": url,
                            "sha256": sha256,
                            "size_bytes": size_bytes,
                            "public": {
                                "license_family": "apache-2.0",
                                "commercial_use": commercial_use,
                                "context_length": 8192,
                                "size_gb": 0.02,
                                "capabilities": ["chat"],
                                "quantization_class": "compact",
                            },
                        }
                    },
                }
            }
        },
    }
    if extra_models:
        models = document["models"]
        assert isinstance(models, dict)
        models.update(extra_models)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def _parse_byte_range(header: str, size: int) -> tuple[int, int]:
    """Parse a ``Range: bytes=start-end`` header.

    Args:
        header: Raw Range header value.
        size: Total payload size in bytes.

    Returns:
        Inclusive start and end offsets.
    """
    unit, _, spec = header.partition("=")
    if unit.strip().lower() != "bytes":
        return 0, size - 1
    start_text, _, end_text = spec.partition("-")
    start = int(start_text) if start_text else 0
    end = int(end_text) if end_text else size - 1
    start = max(0, min(start, size - 1))
    end = max(start, min(end, size - 1))
    return start, end


def _is_forbidden_backend(module_name: str) -> bool:
    """Return whether a module name is a forbidden inference backend.

    Args:
        module_name: Fully qualified module name from ``sys.modules``.

    Returns:
        True when the name is a forbidden backend or a submodule of one.
    """
    return any(
        module_name == backend or module_name.startswith(f"{backend}.")
        for backend in FORBIDDEN_BACKENDS
    )
