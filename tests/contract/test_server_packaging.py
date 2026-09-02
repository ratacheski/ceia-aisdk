"""Contract tests for the ``[server]`` extra, README, and artifact contents."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_server_extra_is_declared() -> None:
    dist = importlib.metadata.distribution("ceia-aisdk")
    extras = dist.metadata.get_all("Provides-Extra") or []
    assert "server" in extras
    requires = dist.metadata.get_all("Requires-Dist") or []
    server_reqs = [
        item for item in requires if 'extra == "server"' in item or "extra == 'server'" in item
    ]
    assert any("fastapi" in item for item in server_reqs)
    assert any("uvicorn" in item for item in server_reqs)


def test_readme_documents_serve_and_tools() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    required = (
        'pip install "ceia-aisdk[server]"',
        "ceia-aisdk serve",
        "http://127.0.0.1:11434/v1",
        "llm/small",
        "tool_calls",
        "--token",
        "--cors",
        "429",
        "--port",
        "reverse proxy",
        "Linux x86_64",
    )
    lowered = readme
    for phrase in required:
        assert phrase in lowered, phrase
    assert "huggingface.co" not in readme.lower() or "opaque" in readme.lower()
    assert "client executes" in readme.lower() or "does not execute" in readme.lower()


def test_source_tree_includes_server_package() -> None:
    server_init = REPO_ROOT / "src" / "ceia_aisdk" / "server" / "__init__.py"
    assert server_init.is_file()


def test_wheel_would_include_server_and_exclude_weights() -> None:
    names = [
        path.relative_to(REPO_ROOT / "src").as_posix()
        for path in (REPO_ROOT / "src" / "ceia_aisdk").rglob("*")
        if path.is_file()
    ]
    assert any(name.startswith("ceia_aisdk/server/") for name in names)
    assert not any(name.endswith((".gguf", ".onnx")) for name in names)
