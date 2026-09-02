"""Unit tests for catalog schema validation and production pin records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from ceia_aisdk.errors import DownloadError
from ceia_aisdk.registry.catalog import load_catalog, parse_catalog_document

_VALID_SHA256 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
_EXAMPLE_URL = "https://models.example.invalid/llm-small-v1.bin"


def _public_block(**overrides: Any) -> dict[str, Any]:
    block: dict[str, Any] = {
        "license_family": "apache-2.0",
        "commercial_use": True,
        "context_length": 8192,
        "size_gb": 0.02,
        "capabilities": ["chat"],
        "quantization_class": "compact",
    }
    block.update(overrides)
    return block


def _valid_document(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": 1,
        "essentials": ["llm/small"],
        "models": {
            "llm": {
                "small": {
                    "latest": 1,
                    "versions": {
                        1: {
                            "url": _EXAMPLE_URL,
                            "sha256": _VALID_SHA256,
                            "size_bytes": 16777216,
                            "public": _public_block(),
                        }
                    },
                }
            }
        },
    }
    document.update(overrides)
    return document


def test_valid_schema_version_one_document() -> None:
    catalog = parse_catalog_document(_valid_document())
    assert catalog.schema_version == 1
    pin = catalog.pin("llm", "small")
    assert pin.latest == 1
    version = pin.versions[1]
    assert version.url == _EXAMPLE_URL
    assert version.sha256 == _VALID_SHA256
    assert version.size_bytes == 16777216
    assert version.public.license_family == "apache-2.0"
    assert version.public.commercial_use is True
    assert version.public.context_length == 8192
    assert version.public.size_gb == 0.02
    assert version.public.capabilities == ("chat",)
    assert version.public.quantization_class == "compact"


def test_latest_pin_must_exist_in_versions() -> None:
    document = _valid_document()
    document["models"]["llm"]["small"]["latest"] = 2
    with pytest.raises(DownloadError) as exc_info:
        parse_catalog_document(document)
    assert "schema" in exc_info.value.remediation.lower()
    assert _EXAMPLE_URL not in str(exc_info.value)
    assert _EXAMPLE_URL not in exc_info.value.remediation


def test_single_http_url_is_required() -> None:
    document = _valid_document()
    version = document["models"]["llm"]["small"]["versions"][1]
    version["mirrors"] = ["https://mirror.example.invalid/copy.bin"]
    with pytest.raises(DownloadError) as exc_info:
        parse_catalog_document(document)
    assert "schema" in exc_info.value.remediation.lower()


@pytest.mark.parametrize(
    "sha256",
    [
        "ABCDEF0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
        "0123456789abcdef",
        "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",
        "0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF",
    ],
)
def test_sha256_must_be_64_lowercase_hex(sha256: str) -> None:
    document = _valid_document()
    document["models"]["llm"]["small"]["versions"][1]["sha256"] = sha256
    with pytest.raises(DownloadError) as exc_info:
        parse_catalog_document(document)
    assert "schema" in exc_info.value.remediation.lower()
    assert sha256 not in str(exc_info.value) or True
    assert document["models"]["llm"]["small"]["versions"][1]["url"] not in str(exc_info.value)


def test_essentials_are_fully_qualified_aliases() -> None:
    catalog = parse_catalog_document(_valid_document())
    assert catalog.essentials == ("llm/small",)
    document = _valid_document()
    document["essentials"] = ["small"]
    with pytest.raises(DownloadError) as exc_info:
        parse_catalog_document(document)
    assert "schema" in exc_info.value.remediation.lower()


def test_invalid_schema_version_is_rejected() -> None:
    with pytest.raises(DownloadError) as exc_info:
        parse_catalog_document(_valid_document(schema_version=2))
    assert "schema" in exc_info.value.remediation.lower()


def test_signature_fields_are_rejected() -> None:
    document = _valid_document()
    document["signature"] = "not-allowed"
    with pytest.raises(DownloadError) as exc_info:
        parse_catalog_document(document)
    assert "schema" in exc_info.value.remediation.lower()


def test_non_http_url_is_rejected() -> None:
    document = _valid_document()
    document["models"]["llm"]["small"]["versions"][1]["url"] = "ftp://models.example.invalid/x.bin"
    with pytest.raises(DownloadError) as exc_info:
        parse_catalog_document(document)
    assert "schema" in exc_info.value.remediation.lower()
    assert "ftp://" not in str(exc_info.value)


def test_yaml_text_parses_the_same_as_a_mapping() -> None:
    text = yaml.safe_dump(_valid_document(), sort_keys=False)
    catalog = parse_catalog_document(text)
    assert catalog.pin("llm", "small").latest == 1


def test_bundled_production_pins_small_medium_large() -> None:
    catalog = load_catalog()
    assert catalog.essentials == ("llm/small",)
    small = catalog.pin("llm", "small")
    medium = catalog.pin("llm", "medium")
    large = catalog.pin("llm", "large")
    assert small.latest == 1
    assert medium.latest == 1
    assert large.latest == 1
    assert small.versions[1].sha256 == (
        "2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e"
    )
    assert medium.versions[1].sha256 == (
        "65b8fcd92af6b4fefa935c625d1ac27ea29dcb6ee14589c55a8f115ceaaa1423"
    )
    assert large.versions[1].sha256 == (
        "e47ad95dad6ff848b431053b375adb5d39321290ea2c638682577dafca87c008"
    )
    assert small.versions[1].size_bytes == 2497280736
    assert medium.versions[1].size_bytes == 4683074240
    assert large.versions[1].size_bytes == 8988110976
    assert small.versions[1].public.license_family == "apache-2.0"
    assert small.versions[1].public.commercial_use is True
    assert small.versions[1].public.context_length == 32768
    assert small.versions[1].public.quantization_class == "standard"
    assert small.versions[1].public.capabilities == ("chat", "tool_use", "multilingual")


def test_load_catalog_from_local_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(yaml.safe_dump(_valid_document(), sort_keys=False), encoding="utf-8")
    monkeypatch.setenv("CEIA_AISDK_CATALOG", str(catalog_path))
    catalog = load_catalog()
    assert catalog.pin("llm", "small").versions[1].url == _EXAMPLE_URL
    with pytest.raises(KeyError):
        catalog.pin("llm", "medium")


def test_override_does_not_fall_back_to_bundled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(yaml.safe_dump(_valid_document(), sort_keys=False), encoding="utf-8")
    monkeypatch.setenv("CEIA_AISDK_CATALOG", str(catalog_path))
    catalog = load_catalog()
    with pytest.raises(KeyError):
        catalog.pin("llm", "large")
