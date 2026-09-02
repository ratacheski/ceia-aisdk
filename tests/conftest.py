"""Shared isolated-home, environment, socket, and import fixtures."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

FORBIDDEN_BACKENDS = (
    "torch",
    "llama_cpp",
    "faster_whisper",
    "piper",
)

_ENV_PREFIX = "CEIA_AISDK_"


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
    Individual tests may opt in with ``@pytest.mark.allow_hosts`` or
    ``enable_socket`` when a future feature requires it.
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
