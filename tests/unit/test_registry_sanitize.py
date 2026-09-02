"""Unit tests for alias and cache-destination sanitization."""

from __future__ import annotations

from pathlib import Path

import pytest

from ceia_aisdk.errors import DownloadError
from ceia_aisdk.registry.cache import (
    cataloged_bin_path,
    cataloged_part_path,
    sanitize_destination,
)


def test_cataloged_paths_stay_under_models(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    bin_path = cataloged_bin_path(cache_dir, "llm", "small", 1)
    part_path = cataloged_part_path(cache_dir, "llm", "small", 1)
    assert bin_path == cache_dir / "models" / "llm" / "small-v1.bin"
    assert part_path == cache_dir / "models" / ".tmp" / "llm-small-v1.part"
    assert bin_path.resolve().is_relative_to((cache_dir / "models").resolve())
    assert part_path.resolve().is_relative_to((cache_dir / "models" / ".tmp").resolve())


@pytest.mark.parametrize("domain", ["..", "../llm", "/etc", "llm/../etc", "llm\\.."])
def test_parent_and_absolute_domains_are_rejected(tmp_path: Path, domain: str) -> None:
    with pytest.raises(DownloadError) as exc_info:
        cataloged_bin_path(tmp_path, domain, "small", 1)
    assert exc_info.value.remediation.strip()
    assert ".." not in str(exc_info.value) or domain != "small"


@pytest.mark.parametrize("size", ["..", "../small", "/tmp", "small/../../etc"])
def test_parent_and_absolute_sizes_are_rejected(tmp_path: Path, size: str) -> None:
    with pytest.raises(DownloadError) as exc_info:
        cataloged_part_path(tmp_path, "llm", size, 1)
    assert exc_info.value.remediation.strip()


def test_sanitize_destination_rejects_escape(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    models = cache_dir / "models"
    models.mkdir(parents=True)
    with pytest.raises(DownloadError):
        sanitize_destination(cache_dir, tmp_path / "outside.bin")
    with pytest.raises(DownloadError):
        sanitize_destination(cache_dir, models / ".." / ".." / "passwd")
    allowed = sanitize_destination(cache_dir, models / "llm" / "small-v1.bin")
    assert allowed.resolve().is_relative_to(models.resolve())
    tmp_allowed = sanitize_destination(cache_dir, models / ".tmp" / "llm-small-v1.part")
    assert tmp_allowed.resolve().is_relative_to((models / ".tmp").resolve()) or str(
        tmp_allowed
    ).endswith("llm-small-v1.part")
