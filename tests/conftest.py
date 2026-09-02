"""Shared isolated-home, environment, socket, import, and model-fixture helpers."""

from __future__ import annotations

import hashlib
import http.server
import json
import os
import shutil
import sys
import threading
from collections.abc import Iterator, Sequence
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
LLM_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
LLM_FIXTURE_PATH = LLM_FIXTURE_DIR / "stories15M-q4_0.gguf"
LLM_FIXTURE_SHA256 = "6151b1929d7f5aa3385d9ddef3393e55587c0a55de661562322bc51dfda93a04"
LLM_FIXTURE_SIZE_BYTES = 19077344


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
    config.addinivalue_line(
        "markers",
        "allow_llama_cpp: allow importing llama_cpp for real-backend LLM tests",
    )
    config.addinivalue_line(
        "markers",
        "requires_llm_fixture: skip when the pinned tiny GGUF fixture is missing",
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
def assert_no_backend_imports(request: pytest.FixtureRequest) -> Iterator[None]:
    """Fail if a test loads a forbidden inference backend.

    Tests marked ``allow_llama_cpp`` may import ``llama_cpp``. Other forbidden
    backends remain blocked.

    Args:
        request: Current pytest test request.

    Yields:
        Control to the test body, then asserts that no forbidden module
        was imported.
    """
    allow_llama_cpp = request.node.get_closest_marker("allow_llama_cpp") is not None
    before = {
        name for name in sys.modules if _is_forbidden_backend(name, allow_llama_cpp=allow_llama_cpp)
    }
    yield
    after = {
        name for name in sys.modules if _is_forbidden_backend(name, allow_llama_cpp=allow_llama_cpp)
    }
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


def _is_forbidden_backend(module_name: str, *, allow_llama_cpp: bool = False) -> bool:
    """Return whether a module name is a forbidden inference backend.

    Args:
        module_name: Fully qualified module name from ``sys.modules``.
        allow_llama_cpp: When true, ``llama_cpp`` is not treated as forbidden.

    Returns:
        True when the name is a forbidden backend or a submodule of one.
    """
    backends = FORBIDDEN_BACKENDS
    if allow_llama_cpp:
        backends = tuple(name for name in backends if name != "llama_cpp")
    return any(
        module_name == backend or module_name.startswith(f"{backend}.") for backend in backends
    )


def skip_if_missing_llm_fixture() -> Path:
    """Return the tiny GGUF path, or skip the calling test when it is absent.

    Returns:
        Absolute path of the pinned stories15M Q4_0 fixture.
    """
    if not LLM_FIXTURE_PATH.is_file():
        pytest.skip("tiny GGUF fixture is missing; run scripts/fetch-llm-test-fixture.sh")
    return LLM_FIXTURE_PATH


@pytest.fixture
def llm_gguf_path() -> Path:
    """Return the pinned tiny GGUF, skipping when the fetch script has not run.

    Returns:
        Absolute path of the fixture file.
    """
    return skip_if_missing_llm_fixture()


@dataclass
class FakeBackend:
    """Recording inference backend used by unit tests instead of llama.cpp."""

    text: str = "ok"
    chunks: tuple[str, ...] = ("ok",)
    raise_oom: bool = False
    raise_overflow: bool = False
    tool_calls: tuple[Any, ...] | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)
    n_gpu_layers: int = 0
    n_ctx: int = 8192
    path: Path | None = None

    def generate(
        self,
        messages: Sequence[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
        seed: int | None,
    ) -> str:
        """Return canned text or raise a backend failure.

        Args:
            messages: Chat messages passed by the LLM wrapper.
            max_tokens: Maximum tokens requested.
            temperature: Sampling temperature.
            seed: Optional generation seed.

        Returns:
            The canned completion text.

        Raises:
            RuntimeError: When OOM or context overflow is requested.
        """
        self.calls.append(
            {
                "kind": "generate",
                "messages": list(messages),
                "max_tokens": max_tokens,
                "temperature": temperature,
                "seed": seed,
            }
        )
        if self.raise_oom:
            raise RuntimeError("CUDA out of memory")
        if self.raise_overflow:
            raise RuntimeError("context overflow: prompt is longer than n_ctx")
        return self.text

    def stream(
        self,
        messages: Sequence[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
        seed: int | None,
    ) -> Iterator[str]:
        """Yield canned chunks or raise a backend failure.

        Args:
            messages: Chat messages passed by the LLM wrapper.
            max_tokens: Maximum tokens requested.
            temperature: Sampling temperature.
            seed: Optional generation seed.

        Yields:
            Canned completion chunks.

        Raises:
            RuntimeError: When OOM or context overflow is requested.
        """
        self.calls.append(
            {
                "kind": "stream",
                "messages": list(messages),
                "max_tokens": max_tokens,
                "temperature": temperature,
                "seed": seed,
            }
        )
        if self.raise_oom:
            raise RuntimeError("CUDA out of memory")
        if self.raise_overflow:
            raise RuntimeError("context overflow: prompt is longer than n_ctx")
        yield from self.chunks

    def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
        seed: int | None,
        tools: object = None,
        tool_choice: object = None,
    ) -> Any:
        """Return canned text or structured tool calls.

        Args:
            messages: Chat messages passed by the LLM wrapper.
            max_tokens: Maximum tokens requested.
            temperature: Sampling temperature.
            seed: Optional generation seed.
            tools: Optional tool declarations.
            tool_choice: Optional tool-choice value.

        Returns:
            A ``CompletionResult`` when tool calls are configured, else text
            wrapped by the caller.
        """
        from ceia_aisdk.llm.tools import CompletionResult

        self.calls.append(
            {
                "kind": "complete",
                "messages": list(messages),
                "max_tokens": max_tokens,
                "temperature": temperature,
                "seed": seed,
                "tools": tools,
                "tool_choice": tool_choice,
            }
        )
        if self.raise_oom:
            raise RuntimeError("CUDA out of memory")
        if self.raise_overflow:
            raise RuntimeError("context overflow: prompt is longer than n_ctx")
        if self.tool_calls:
            return CompletionResult(tool_calls=tuple(self.tool_calls))
        return CompletionResult(content=self.text)


@pytest.fixture
def fake_backend(monkeypatch: pytest.MonkeyPatch) -> FakeBackend:
    """Install a fake inference backend in place of llama.cpp.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        The installed fake backend instance.
    """
    backend = FakeBackend()

    def _create(
        path: Path,
        *,
        n_ctx: int,
        n_gpu_layers: int,
    ) -> FakeBackend:
        backend.path = path
        backend.n_ctx = n_ctx
        backend.n_gpu_layers = n_gpu_layers
        return backend

    monkeypatch.setattr("ceia_aisdk.llm.backend.create_backend", _create)
    monkeypatch.setattr("ceia_aisdk.llm.model.create_backend", _create)
    return backend


def seed_cataloged_cache(
    cache_dir: Path,
    source: Path,
    *,
    domain: str = "llm",
    size: str = "small",
    version: int = 1,
    alias: str = "llm/small@1",
    sha256: str = LLM_FIXTURE_SHA256,
    size_bytes: int = LLM_FIXTURE_SIZE_BYTES,
) -> Path:
    """Copy a fixture into the opaque cataloged cache layout.

    Args:
        cache_dir: Isolated SDK cache directory.
        source: Local fixture file to copy.
        domain: Catalog domain token.
        size: Catalog size token.
        version: Catalog version.
        alias: Canonical alias stored in the sidecar.
        sha256: Checksum recorded in the sidecar.
        size_bytes: Declared payload size.

    Returns:
        Destination cache path.
    """
    destination = cache_dir / "models" / domain / f"{size}-v{version}.bin"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    sidecar = destination.with_name(f"{size}-v{version}.meta.json")
    sidecar.write_text(
        json.dumps(
            {
                "alias": alias,
                "source": "catalog",
                "sha256": sha256,
                "size_bytes": size_bytes,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


@pytest.fixture
def llm_fixture_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_cache_dir: Path,
    llm_gguf_path: Path,
) -> Path:
    """Install a loopback-free catalog and seed cache with the tiny GGUF.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.
        isolated_cache_dir: Isolated cache directory.
        llm_gguf_path: Pinned tiny GGUF path.

    Returns:
        The isolated cache directory. ``CEIA_AISDK_CATALOG`` is set.
    """
    catalog_path = tmp_path / "llm-fixture-catalog.yaml"
    write_catalog_yaml(
        catalog_path,
        url="https://example.invalid/stories15M-q4_0.gguf",
        sha256=LLM_FIXTURE_SHA256,
        size_bytes=LLM_FIXTURE_SIZE_BYTES,
        extra_models={
            "llm": {
                "small": {
                    "latest": 1,
                    "versions": {
                        1: {
                            "url": "https://example.invalid/stories15M-q4_0.gguf",
                            "sha256": LLM_FIXTURE_SHA256,
                            "size_bytes": LLM_FIXTURE_SIZE_BYTES,
                            "public": {
                                "license_family": "apache-2.0",
                                "commercial_use": True,
                                "context_length": 2048,
                                "size_gb": 0.02,
                                "capabilities": ["chat"],
                                "quantization_class": "compact",
                            },
                        }
                    },
                },
                "medium": {
                    "latest": 1,
                    "versions": {
                        1: {
                            "url": "https://example.invalid/stories15M-medium.gguf",
                            "sha256": LLM_FIXTURE_SHA256,
                            "size_bytes": LLM_FIXTURE_SIZE_BYTES,
                            "public": {
                                "license_family": "apache-2.0",
                                "commercial_use": True,
                                "context_length": 2048,
                                "size_gb": 0.02,
                                "capabilities": ["chat", "tool_use"],
                                "quantization_class": "compact",
                            },
                        }
                    },
                },
            }
        },
    )
    monkeypatch.setenv("CEIA_AISDK_CATALOG", str(catalog_path))
    seed_cataloged_cache(isolated_cache_dir, llm_gguf_path)
    seed_cataloged_cache(
        isolated_cache_dir,
        llm_gguf_path,
        size="medium",
        alias="llm/medium@1",
    )
    return isolated_cache_dir


@pytest.fixture
def fake_llm_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_cache_dir: Path,
) -> Path:
    """Install a local catalog and a tiny dummy cache file for fake-backend tests.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.
        isolated_cache_dir: Isolated cache directory.

    Returns:
        The isolated cache directory.
    """
    dummy = tmp_path / "dummy.bin"
    dummy.write_bytes(b"not-a-gguf")
    digest = hashlib.sha256(dummy.read_bytes()).hexdigest()
    catalog_path = tmp_path / "fake-llm-catalog.yaml"
    write_catalog_yaml(
        catalog_path,
        url="https://example.invalid/dummy.bin",
        sha256=digest,
        size_bytes=dummy.stat().st_size,
        extra_models={
            "llm": {
                "small": {
                    "latest": 1,
                    "versions": {
                        1: {
                            "url": "https://example.invalid/dummy.bin",
                            "sha256": digest,
                            "size_bytes": dummy.stat().st_size,
                            "public": {
                                "license_family": "apache-2.0",
                                "commercial_use": True,
                                "context_length": 8192,
                                "size_gb": 2.33,
                                "capabilities": ["chat"],
                                "quantization_class": "compact",
                            },
                        }
                    },
                },
                "medium": {
                    "latest": 1,
                    "versions": {
                        1: {
                            "url": "https://example.invalid/dummy-medium.bin",
                            "sha256": digest,
                            "size_bytes": dummy.stat().st_size,
                            "public": {
                                "license_family": "apache-2.0",
                                "commercial_use": True,
                                "context_length": 8192,
                                "size_gb": 99.0,
                                "capabilities": ["chat", "tool_use"],
                                "quantization_class": "standard",
                            },
                        }
                    },
                },
            }
        },
    )
    monkeypatch.setenv("CEIA_AISDK_CATALOG", str(catalog_path))
    seed_cataloged_cache(
        isolated_cache_dir,
        dummy,
        sha256=digest,
        size_bytes=dummy.stat().st_size,
    )
    seed_cataloged_cache(
        isolated_cache_dir,
        dummy,
        size="medium",
        alias="llm/medium@1",
        sha256=digest,
        size_bytes=dummy.stat().st_size,
    )
    return isolated_cache_dir
