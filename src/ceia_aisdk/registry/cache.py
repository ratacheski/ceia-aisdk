"""Local model cache layout, destination sanitization, locks, and promotion.

Cataloged artifacts live under ``<cache_dir>/models/<domain>/`` with opaque
basenames. Writes cannot escape ``models`` or ``models/.tmp``.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from ceia_aisdk.config import AISDKConfig
from ceia_aisdk.errors import DownloadError
from ceia_aisdk.registry.catalog import resolve_internal

_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SANITIZE_REMEDIATION = (
    "Use a cataloged alias of the form domain/size@N with lowercase tokens, "
    "and keep cache writes under the configured cache directory models tree."
)
_OFFLINE_REMEDIATION = (
    "Unset CEIA_AISDK_OFFLINE or pass offline=false, then retry "
    "ceia-aisdk model pull while a network path to the cataloged artifact "
    "is available."
)
_LOCK_REMEDIATION = (
    "Retry on a local Linux filesystem that supports fcntl locks, and avoid "
    "holding another process on the same alias."
)


def cataloged_bin_path(cache_dir: Path, domain: str, size: str, version: int) -> Path:
    """Return the opaque final path for a cataloged artifact.

    Args:
        cache_dir: Configured cache directory.
        domain: Catalog domain token such as ``llm``.
        size: Size token such as ``small``.
        version: Positive integer version.

    Returns:
        ``<cache_dir>/models/<domain>/<size>-v<N>.bin`` after sanitization.

    Raises:
        DownloadError: If the tokens or destination would escape the cache.
    """
    domain_token, size_token, version_n = _cataloged_parts(domain, size, version)
    destination = cache_dir / "models" / domain_token / f"{size_token}-v{version_n}.bin"
    return sanitize_destination(cache_dir, destination)


def cataloged_part_path(cache_dir: Path, domain: str, size: str, version: int) -> Path:
    """Return the opaque partial-download path for a cataloged artifact.

    Args:
        cache_dir: Configured cache directory.
        domain: Catalog domain token such as ``llm``.
        size: Size token such as ``small``.
        version: Positive integer version.

    Returns:
        ``<cache_dir>/models/.tmp/<domain>-<size>-v<N>.part`` after sanitization.

    Raises:
        DownloadError: If the tokens or destination would escape the cache.
    """
    domain_token, size_token, version_n = _cataloged_parts(domain, size, version)
    destination = cache_dir / "models" / ".tmp" / f"{domain_token}-{size_token}-v{version_n}.part"
    return sanitize_destination(cache_dir, destination)


def cataloged_meta_path(cache_dir: Path, domain: str, size: str, version: int) -> Path:
    """Return the sidecar metadata path for a cataloged artifact.

    Args:
        cache_dir: Configured cache directory.
        domain: Catalog domain token.
        size: Size token.
        version: Positive integer version.

    Returns:
        ``<cache_dir>/models/<domain>/<size>-v<N>.meta.json``.

    Raises:
        DownloadError: If the destination would escape the cache.
    """
    domain_token, size_token, version_n = _cataloged_parts(domain, size, version)
    destination = cache_dir / "models" / domain_token / f"{size_token}-v{version_n}.meta.json"
    return sanitize_destination(cache_dir, destination)


def cataloged_lock_path(cache_dir: Path, domain: str, size: str, version: int) -> Path:
    """Return the exclusive lock path for a cataloged artifact.

    Args:
        cache_dir: Configured cache directory.
        domain: Catalog domain token.
        size: Size token.
        version: Positive integer version.

    Returns:
        ``<cache_dir>/models/<domain>/<size>-v<N>.lock``.

    Raises:
        DownloadError: If the destination would escape the cache.
    """
    domain_token, size_token, version_n = _cataloged_parts(domain, size, version)
    destination = cache_dir / "models" / domain_token / f"{size_token}-v{version_n}.lock"
    return sanitize_destination(cache_dir, destination)


def sanitize_destination(cache_dir: Path, destination: Path) -> Path:
    """Resolve a destination and reject paths outside the model cache.

    Allowed roots are ``<cache_dir>/models`` and ``<cache_dir>/models/.tmp``.

    Args:
        cache_dir: Configured cache directory.
        destination: Candidate path, which may not exist yet.

    Returns:
        The resolved destination path.

    Raises:
        DownloadError: If the resolved path escapes the allowed roots.
    """
    models_root = (cache_dir / "models").resolve()
    tmp_root = (cache_dir / "models" / ".tmp").resolve()
    try:
        resolved = destination.resolve()
    except OSError as exc:
        raise DownloadError(
            "The cache destination could not be resolved.",
            remediation=_SANITIZE_REMEDIATION,
        ) from exc
    if _is_within(resolved, tmp_root) or _is_within(resolved, models_root):
        return resolved
    raise DownloadError(
        "Refusing to write a model file outside the cache models directory.",
        remediation=_SANITIZE_REMEDIATION,
    )


def ensure_local(
    alias: str,
    *,
    config: AISDKConfig | None = None,
    domain: str | None = None,
    progress: Callable[[int, int | None], None] | None = None,
) -> Path:
    """Return a verified local path, downloading when needed.

    Args:
        alias: Cataloged alias such as ``llm/small``, or a documented bypass.
        config: Effective configuration. Defaults to ``AISDKConfig.load()``.
        domain: Domain context for an unqualified size token.
        progress: Optional ``(bytes_have, bytes_expected)`` callback used by the CLI.

    Returns:
        The opaque cache path of the verified artifact.

    Raises:
        ModelNotFoundError: If the alias is not in the active catalog.
        DownloadError: On offline miss, transfer failure, integrity failure, or lock failure.
    """
    effective = config if config is not None else AISDKConfig.load()
    if _is_bypass_token(alias):
        return _ensure_bypass(alias, config=effective, progress=progress)
    resolved, entry = resolve_internal(alias, config=effective, domain=domain)
    bin_path = cataloged_bin_path(
        effective.cache_dir, resolved.domain, resolved.size, resolved.version
    )
    part_path = cataloged_part_path(
        effective.cache_dir, resolved.domain, resolved.size, resolved.version
    )
    meta_path = cataloged_meta_path(
        effective.cache_dir, resolved.domain, resolved.size, resolved.version
    )
    lock_path = cataloged_lock_path(
        effective.cache_dir, resolved.domain, resolved.size, resolved.version
    )
    bin_path.parent.mkdir(parents=True, exist_ok=True)
    part_path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_lock(lock_path):
        if _is_valid_cataloged(bin_path, meta_path, entry.sha256, entry.size_bytes):
            return bin_path
        if bin_path.is_file():
            bin_path.unlink()
            meta_path.unlink(missing_ok=True)
        if effective.offline:
            raise DownloadError(
                "The alias is not available in the local cache while offline mode is enabled.",
                remediation=_OFFLINE_REMEDIATION,
            )
        from ceia_aisdk.registry.downloader import download_http

        download_http(
            entry.url,
            part_path,
            expected_sha256=entry.sha256,
            expected_size=entry.size_bytes,
            progress=progress,
            offline=False,
        )
        os.replace(part_path, bin_path)
        _write_sidecar(
            meta_path,
            alias=resolved.alias,
            source="catalog",
            sha256=entry.sha256,
            size_bytes=entry.size_bytes,
        )
        return bin_path


def custom_bin_path(cache_dir: Path, basename: str) -> Path:
    """Return a sanitized custom-cache path for a bypass artifact.

    Args:
        cache_dir: Configured cache directory.
        basename: Original filename to preserve.

    Returns:
        ``<cache_dir>/models/custom/<basename>`` after sanitization.

    Raises:
        DownloadError: If the basename would escape the cache.
    """
    safe = _sanitize_basename(basename)
    destination = cache_dir / "models" / "custom" / safe
    return sanitize_destination(cache_dir, destination)


def _ensure_bypass(
    alias: str,
    *,
    config: AISDKConfig,
    progress: Callable[[int, int | None], None] | None,
) -> Path:
    """Store an ``hf://`` or filesystem-path bypass under ``models/custom/``.

    Args:
        alias: Bypass token.
        config: Effective configuration.
        progress: Optional download progress callback.

    Returns:
        The custom cache path.

    Raises:
        DownloadError: If the source is missing, offline, or the copy fails.
    """
    if alias.startswith("hf://"):
        return _ensure_hf_bypass(alias, config=config, progress=progress)
    return _ensure_path_bypass(alias, config=config)


def _ensure_hf_bypass(
    alias: str,
    *,
    config: AISDKConfig,
    progress: Callable[[int, int | None], None] | None,
) -> Path:
    """Download an ``hf://`` token into ``models/custom``.

    Args:
        alias: ``hf://repo/file`` token.
        config: Effective configuration.
        progress: Optional progress callback.

    Returns:
        The custom cache path.

    Raises:
        DownloadError: If the token is malformed, offline, or the transfer fails.
    """
    source_name = alias.rsplit("/", 1)[-1] or "model.bin"
    url = _hf_url(alias)
    destination = custom_bin_path(config.cache_dir, source_name)
    part = sanitize_destination(
        config.cache_dir,
        config.cache_dir / "models" / ".tmp" / f"custom-{destination.name}.part",
    )
    meta = destination.with_name(destination.name + ".meta.json")
    lock = destination.with_name(destination.name + ".lock")
    destination.parent.mkdir(parents=True, exist_ok=True)
    part.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_lock(lock):
        if destination.is_file():
            return destination
        if config.offline:
            raise DownloadError(
                "The bypass source is not available in the local cache while offline.",
                remediation=_OFFLINE_REMEDIATION,
            )
        from ceia_aisdk.registry.downloader import download_http

        digest = download_http(
            url,
            part,
            expected_sha256=None,
            progress=progress,
            offline=False,
        )
        os.replace(part, destination)
        _write_sidecar(
            meta,
            alias=alias,
            source="bypass",
            sha256=digest,
            size_bytes=destination.stat().st_size,
        )
        return destination


def _ensure_path_bypass(alias: str, *, config: AISDKConfig) -> Path:
    """Copy a local file into ``models/custom``.

    Args:
        alias: Filesystem path.
        config: Effective configuration.

    Returns:
        The custom cache path.

    Raises:
        DownloadError: If the source is missing or cannot be copied.
    """
    path = Path(alias).expanduser()
    if not path.is_file():
        raise DownloadError(
            "The local model path does not exist.",
            remediation="Pass an existing file path or a cataloged alias such as llm/small.",
        )
    destination = custom_bin_path(config.cache_dir, path.name)
    meta = destination.with_name(destination.name + ".meta.json")
    lock = destination.with_name(destination.name + ".lock")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_lock(lock):
        if destination.is_file():
            return destination
        try:
            destination.write_bytes(path.read_bytes())
        except OSError as exc:
            raise DownloadError(
                "The local model file could not be copied into the cache.",
                remediation=(
                    "Ensure the source file is readable and the cache directory is writable."
                ),
            ) from exc
        from ceia_aisdk.registry.downloader import sha256_file

        _write_sidecar(
            meta,
            alias=str(path.resolve()),
            source="bypass",
            sha256=sha256_file(destination),
            size_bytes=destination.stat().st_size,
        )
        return destination


def _is_bypass_token(alias: str) -> bool:
    """Return whether ``alias`` is an ``hf://`` token or a filesystem path.

    Args:
        alias: User-supplied token.

    Returns:
        True when the token should skip catalog resolution.
    """
    if alias.startswith("hf://"):
        return True
    if alias.startswith(("/", ".", "~")):
        return True
    expanded = Path(alias).expanduser()
    return expanded.is_file()


def _sanitize_basename(basename: str) -> str:
    """Return a filename that cannot escape ``models/custom``.

    Args:
        basename: Original filename.

    Returns:
        A safe basename.

    Raises:
        DownloadError: If the name is empty or contains path elements.
    """
    name = Path(basename).name
    if not name or name in {".", ".."} or "/" in name or "\\" in name or "\x00" in name:
        raise DownloadError(
            "The bypass filename is not a safe cache basename.",
            remediation="Use a simple filename without path separators.",
        )
    return name


def _hf_url(token: str) -> str:
    """Convert ``hf://repo/file`` into an HTTPS Hugging Face resolve URL.

    Args:
        token: Bypass token beginning with ``hf://``.

    Returns:
        An ``https://huggingface.co/.../resolve/main/...`` URL.

    Raises:
        DownloadError: If the token is malformed.
    """
    rest = token[5:]
    if "/" not in rest or ".." in rest:
        raise DownloadError(
            "The hf:// bypass token is malformed.",
            remediation="Use hf://<repo>/<file> such as hf://org/model/weights.gguf.",
        )
    repo, _, filename = rest.rpartition("/")
    if not repo or not filename:
        raise DownloadError(
            "The hf:// bypass token is malformed.",
            remediation="Use hf://<repo>/<file> such as hf://org/model/weights.gguf.",
        )
    return f"https://huggingface.co/{repo}/resolve/main/{filename}"


def cached_path(
    alias: str,
    *,
    config: AISDKConfig | None = None,
    domain: str | None = None,
) -> Path:
    """Return the absolute cache path when a cataloged alias is already cached.

    Args:
        alias: Cataloged alias.
        config: Effective configuration.
        domain: Domain context for unqualified names.

    Returns:
        The existing ``.bin`` path.

    Raises:
        DownloadError: If the alias is not cached.
        ModelNotFoundError: If the alias is not in the catalog.
    """
    effective = config if config is not None else AISDKConfig.load()
    resolved, _entry = resolve_internal(alias, config=effective, domain=domain)
    bin_path = cataloged_bin_path(
        effective.cache_dir, resolved.domain, resolved.size, resolved.version
    )
    if not bin_path.is_file():
        raise DownloadError(
            "The alias is not present in the local model cache.",
            remediation="Run ceia-aisdk model pull for this alias, then retry model where.",
        )
    return bin_path


def verify_cached_artifacts(*, config: AISDKConfig | None = None) -> list[Path]:
    """Rehash cached cataloged artifacts and return mismatched paths.

    Args:
        config: Effective configuration.

    Returns:
        Paths whose SHA-256 does not match the sidecar or catalog.

    Raises:
        DownloadError: If a cached file cannot be read.
    """
    from ceia_aisdk.registry.downloader import sha256_file

    effective = config if config is not None else AISDKConfig.load()
    mismatches: list[Path] = []
    for bin_path, meta in _iter_cataloged_cache(effective.cache_dir):
        expected = meta.get("sha256")
        if not isinstance(expected, str) or sha256_file(bin_path) != expected:
            mismatches.append(bin_path)
    return mismatches


def list_cached_artifacts(*, config: AISDKConfig | None = None) -> list[tuple[str, int]]:
    """List cached cataloged aliases and file sizes.

    Args:
        config: Effective configuration.

    Returns:
        Pairs of alias string and size in bytes.
    """
    effective = config if config is not None else AISDKConfig.load()
    items: list[tuple[str, int]] = []
    for bin_path, meta in _iter_cataloged_cache(effective.cache_dir):
        alias = meta.get("alias")
        label = alias if isinstance(alias, str) and alias else bin_path.name
        items.append((label, bin_path.stat().st_size))
    return items


def remove_cached_alias(
    alias: str,
    *,
    config: AISDKConfig | None = None,
    domain: str | None = None,
) -> None:
    """Delete a cached alias, sidecar, lock, and leftover partial.

    Args:
        alias: Cataloged alias.
        config: Effective configuration.
        domain: Domain context for unqualified names.

    Raises:
        DownloadError: If the alias is not cached.
        ModelNotFoundError: If the alias is not in the catalog.
    """
    effective = config if config is not None else AISDKConfig.load()
    resolved, _entry = resolve_internal(alias, config=effective, domain=domain)
    bin_path = cataloged_bin_path(
        effective.cache_dir, resolved.domain, resolved.size, resolved.version
    )
    part_path = cataloged_part_path(
        effective.cache_dir, resolved.domain, resolved.size, resolved.version
    )
    meta_path = cataloged_meta_path(
        effective.cache_dir, resolved.domain, resolved.size, resolved.version
    )
    lock_path = cataloged_lock_path(
        effective.cache_dir, resolved.domain, resolved.size, resolved.version
    )
    if not bin_path.is_file() and not part_path.is_file():
        raise DownloadError(
            "The alias is not present in the local model cache.",
            remediation="Run ceia-aisdk model pull for this alias before model rm.",
        )
    bin_path.unlink(missing_ok=True)
    meta_path.unlink(missing_ok=True)
    part_path.unlink(missing_ok=True)
    lock_path.unlink(missing_ok=True)


def _cataloged_parts(domain: str, size: str, version: int) -> tuple[str, str, int]:
    """Validate domain, size, and version tokens.

    Args:
        domain: Domain token.
        size: Size token.
        version: Version integer.

    Returns:
        Validated domain, size, and version.

    Raises:
        DownloadError: If any token is invalid.
    """
    return _require_token(domain, "domain"), _require_token(size, "size"), _require_version(version)


@contextlib.contextmanager
def _exclusive_lock(lock_path: Path) -> Iterator[None]:
    """Acquire an exclusive ``fcntl.flock`` on ``lock_path``.

    Args:
        lock_path: Sibling lock file for one artifact.

    Yields:
        Control to the locked critical section.

    Raises:
        DownloadError: If flock is unsupported or cannot be acquired.
    """
    try:
        import fcntl
    except ImportError as exc:  # pragma: no cover - Linux always provides fcntl
        raise DownloadError(
            "Exclusive cache locks are unavailable on this platform.",
            remediation=_LOCK_REMEDIATION,
        ) from exc
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except OSError as exc:
            raise DownloadError(
                "Could not lock the model cache for this alias.",
                remediation=_LOCK_REMEDIATION,
            ) from exc
        yield
    finally:
        handle.close()


def _is_valid_cataloged(bin_path: Path, meta_path: Path, sha256: str, size_bytes: int) -> bool:
    """Return whether a cached cataloged file matches the catalog pin.

    Args:
        bin_path: Final artifact path.
        meta_path: Sidecar path.
        sha256: Catalog SHA-256.
        size_bytes: Catalog size.

    Returns:
        True when the file exists, size matches, and the sidecar hash matches.
    """
    if not bin_path.is_file():
        return False
    try:
        if bin_path.stat().st_size != size_bytes:
            return False
    except OSError:
        return False
    meta = _read_sidecar(meta_path)
    if meta is None:
        return False
    return meta.get("source") == "catalog" and meta.get("sha256") == sha256


def _write_sidecar(
    path: Path,
    *,
    alias: str | None,
    source: str,
    sha256: str | None,
    size_bytes: int,
) -> None:
    """Write artifact sidecar JSON.

    Args:
        path: Sidecar destination.
        alias: Canonical alias, if cataloged.
        source: ``catalog`` or ``bypass``.
        sha256: Digest when known.
        size_bytes: File size.

    Raises:
        DownloadError: If the sidecar cannot be written.
    """
    payload = {
        "alias": alias,
        "source": source,
        "sha256": sha256,
        "size_bytes": size_bytes,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise DownloadError(
            "The cache sidecar could not be written.",
            remediation="Ensure the cache directory is writable and retry ceia-aisdk model pull.",
        ) from exc


def _read_sidecar(path: Path) -> dict[str, Any] | None:
    """Read sidecar JSON if present.

    Args:
        path: Sidecar path.

    Returns:
        Parsed mapping, or ``None`` when missing or invalid.
    """
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _iter_cataloged_cache(cache_dir: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Yield cached cataloged artifacts and their sidecars.

    Args:
        cache_dir: Configured cache directory.

    Yields:
        Pairs of ``.bin`` path and sidecar mapping.
    """
    models = cache_dir / "models"
    if not models.is_dir():
        return
    for bin_path in sorted(models.rglob("*.bin")):
        if bin_path.parent.name == "custom" or ".tmp" in bin_path.parts:
            continue
        meta_path = bin_path.with_name(bin_path.name[:-4] + ".meta.json")
        meta = _read_sidecar(meta_path)
        if meta is None or meta.get("source") != "catalog":
            continue
        yield bin_path, meta


def _require_token(value: str, label: str) -> str:
    """Return a validated domain or size token.

    Args:
        value: Candidate token.
        label: Field name used in the error message.

    Returns:
        The token.

    Raises:
        DownloadError: If the token is empty, contains ``..``, or is not a
            lowercase identifier.
    """
    if not isinstance(value, str) or not value or "\x00" in value:
        raise DownloadError(
            f"The cache {label} token is invalid.",
            remediation=_SANITIZE_REMEDIATION,
        )
    if ".." in value or value.startswith("/") or "\\" in value or "/" in value:
        raise DownloadError(
            f"The cache {label} token must not contain path separators or '..'.",
            remediation=_SANITIZE_REMEDIATION,
        )
    if not _TOKEN_RE.fullmatch(value):
        raise DownloadError(
            f"The cache {label} token must be a lowercase alphanumeric name.",
            remediation=_SANITIZE_REMEDIATION,
        )
    return value


def _require_version(version: int) -> int:
    """Return a validated positive version integer.

    Args:
        version: Candidate version.

    Returns:
        The version.

    Raises:
        DownloadError: If the version is not a positive integer.
    """
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise DownloadError(
            "The cache version must be a positive integer.",
            remediation=_SANITIZE_REMEDIATION,
        )
    return version


def _is_within(path: Path, root: Path) -> bool:
    """Return whether ``path`` is ``root`` or a descendant of ``root``.

    Args:
        path: Resolved candidate path.
        root: Resolved allowed root.

    Returns:
        True when ``path`` is inside ``root``.
    """
    return path == root or root in path.parents
