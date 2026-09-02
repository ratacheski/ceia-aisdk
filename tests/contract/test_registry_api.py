"""Contract tests for the public registry API."""

from __future__ import annotations

import inspect
from pathlib import Path

from ceia_aisdk.registry import resolve
from ceia_aisdk.registry.catalog import ResolvedAlias


def test_resolve_signature_is_keyword_only_after_alias() -> None:
    signature = inspect.signature(resolve)
    parameters = list(signature.parameters.values())
    assert parameters[0].name == "alias"
    assert parameters[0].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    for parameter in parameters[1:]:
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert "config" in signature.parameters
    assert "domain" in signature.parameters
    assert signature.return_annotation is ResolvedAlias or "ResolvedAlias" in str(
        signature.return_annotation
    )


def test_resolved_alias_is_opaque() -> None:
    resolved = resolve("llm/small")
    text = repr(resolved) + str(resolved) + resolved.alias
    assert "huggingface.co" not in text
    assert "model.gguf" not in text
    assert "http://" not in text
    assert "https://" not in text
    assert not hasattr(resolved, "url")
    assert not hasattr(resolved, "sha256")
    public_fields = set(resolved.__dataclass_fields__)
    assert public_fields == {"alias", "domain", "size", "version", "public"}


def test_resolve_does_not_download_or_write(isolated_cache_dir: Path) -> None:
    resolved = resolve("llm/small")
    assert resolved.version == 1
    cache_files = list(isolated_cache_dir.rglob("*") if isolated_cache_dir.exists() else [])
    assert not any(path.is_file() for path in cache_files)


def test_get_public_metadata_exposes_only_public_fields() -> None:
    from ceia_aisdk.registry import get_public_metadata

    meta = get_public_metadata("llm/small")
    assert meta.license_family
    assert meta.commercial_use is True
    assert meta.context_length == 32768
    assert meta.size_gb > 0
    assert meta.capabilities
    assert meta.quantization_class == "standard"
    assert not hasattr(meta, "url")
    assert not hasattr(meta, "sha256")
    text = repr(meta)
    assert "huggingface.co" not in text
    assert "model.gguf" not in text
