"""Unit tests for versioned alias resolution without downloading."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ceia_aisdk.errors import ModelNotFoundError
from ceia_aisdk.registry import resolve
from ceia_aisdk.registry.catalog import ResolvedAlias


def test_domain_qualified_alias_pins_latest() -> None:
    resolved = resolve("llm/small")
    assert isinstance(resolved, ResolvedAlias)
    assert resolved.alias == "llm/small@1"
    assert resolved.domain == "llm"
    assert resolved.size == "small"
    assert resolved.version == 1
    assert resolved.public.quantization_class == "standard"


def test_explicit_version_and_latest_are_the_same_pin() -> None:
    latest = resolve("llm/small@latest")
    pinned = resolve("llm/small@1")
    unqualified = resolve("llm/small")
    assert latest.alias == pinned.alias == unqualified.alias == "llm/small@1"
    assert latest.version == pinned.version == 1


def test_medium_and_large_aliases_resolve() -> None:
    assert resolve("llm/medium").alias == "llm/medium@1"
    assert resolve("llm/large").alias == "llm/large@1"


def test_programmatic_unqualified_small_is_rejected() -> None:
    with pytest.raises(ModelNotFoundError) as exc_info:
        resolve("small")
    assert "domain" in str(exc_info.value).lower() or "llm/small" in exc_info.value.remediation


def test_unqualified_small_with_domain_context_resolves() -> None:
    resolved = resolve("small", domain="llm")
    assert resolved.alias == "llm/small@1"


def test_unknown_alias_suggests_same_domain() -> None:
    with pytest.raises(ModelNotFoundError) as exc_info:
        resolve("llm/tiny")
    error = exc_info.value
    assert error.remediation.strip()
    lowered = error.remediation.lower()
    assert "llm/small" in lowered
    assert "huggingface.co" not in str(error)
    assert "huggingface.co" not in error.remediation


def test_resolve_does_not_create_cache_files(isolated_cache_dir: Path) -> None:
    resolve("llm/small")
    models = isolated_cache_dir / "models"
    assert not models.exists() or not any(models.rglob("*"))


def test_resolve_does_not_import_httpx() -> None:
    before = "httpx" in sys.modules
    resolve("llm/small")
    if not before:
        assert "httpx" not in sys.modules
