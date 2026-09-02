"""Resumable HTTP download of cataloged model artifacts.

``httpx`` is imported only inside download functions so a lightweight
``import ceia_aisdk`` does not pay the HTTP-client cost.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from ceia_aisdk._logging import get_logger
from ceia_aisdk.errors import DownloadError

_LOGGER = get_logger(__name__)
_CHUNK_SIZE = 1024 * 1024
_CONNECT_TIMEOUT = 10.0
_READ_TIMEOUT = 60.0
_DOWNLOAD_REMEDIATION = (
    "Retry ceia-aisdk model pull, check network access, or set "
    "CEIA_AISDK_CATALOG to a reachable catalog. Run ceia-aisdk model verify "
    "after a failed transfer."
)
_OFFLINE_REMEDIATION = (
    "Unset CEIA_AISDK_OFFLINE or pass offline=false, then retry "
    "ceia-aisdk model pull while a network path to the cataloged artifact "
    "is available."
)


def download_http(
    url: str,
    part_path: Path,
    *,
    expected_sha256: str | None,
    expected_size: int | None = None,
    progress: Callable[[int, int | None], None] | None = None,
    offline: bool = False,
) -> str:
    """Download or resume ``url`` into ``part_path`` and optionally verify SHA-256.

    Args:
        url: Single download location. Never logged at WARNING or ERROR.
        part_path: Temporary destination already sanitized into the cache tree.
        expected_sha256: 64-character lowercase hex digest, or ``None`` for bypasses.
        expected_size: Declared size in bytes, if known.
        progress: Optional callback of ``(bytes_have, bytes_expected)``.
        offline: When true, refuse to open an HTTP client.

    Returns:
        The SHA-256 hex digest of the downloaded file.

    Raises:
        DownloadError: On offline mode, HTTP failure, or checksum mismatch.
    """
    if offline:
        raise DownloadError(
            "Refusing to download while offline mode is enabled.",
            remediation=_OFFLINE_REMEDIATION,
        )
    import httpx

    host = urlparse(url).hostname or "unknown-host"
    _LOGGER.debug("Downloading cataloged artifact from host %s", host)
    part_path.parent.mkdir(parents=True, exist_ok=True)
    existing = part_path.stat().st_size if part_path.is_file() else 0
    headers: dict[str, str] = {}
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"
    timeout = httpx.Timeout(_CONNECT_TIMEOUT, read=_READ_TIMEOUT)
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            with client.stream("GET", url, headers=headers) as response:
                _consume_stream(
                    response,
                    part_path,
                    existing=existing,
                    expected_size=expected_size,
                    progress=progress,
                )
    except DownloadError:
        raise
    except httpx.HTTPError as exc:
        _LOGGER.error("Cataloged artifact download failed from host %s", host)
        raise DownloadError(
            "The cataloged artifact could not be downloaded.",
            remediation=_DOWNLOAD_REMEDIATION,
        ) from exc
    digest = sha256_file(part_path)
    if expected_sha256 is not None and digest != expected_sha256:
        part_path.unlink(missing_ok=True)
        raise DownloadError(
            "The downloaded artifact failed the catalog checksum and was discarded.",
            remediation=_DOWNLOAD_REMEDIATION,
        )
    _fsync_file(part_path)
    return digest


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file.

    Args:
        path: File to hash.

    Returns:
        Lowercase hex digest.

    Raises:
        DownloadError: If the file cannot be read.
    """
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(_CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError as exc:
        raise DownloadError(
            "The cached artifact could not be read for checksum verification.",
            remediation="Run ceia-aisdk model verify or delete the cache entry and pull again.",
        ) from exc
    return digest.hexdigest()


def _consume_stream(
    response: object,
    part_path: Path,
    *,
    existing: int,
    expected_size: int | None,
    progress: Callable[[int, int | None], None] | None,
) -> None:
    """Write an HTTP response body onto the part file.

    Args:
        response: ``httpx`` streaming response.
        part_path: Partial destination.
        existing: Bytes already present when a Range request was issued.
        expected_size: Catalog size, if known.
        progress: Optional progress callback.

    Raises:
        DownloadError: If the status code is not a successful download or resume.
    """
    status = int(getattr(response, "status_code", 0))
    if existing > 0 and status == 206:
        mode = "ab"
        have = existing
    elif existing > 0 and status == 200:
        mode = "wb"
        have = 0
    elif existing == 0 and status == 200:
        mode = "wb"
        have = 0
    else:
        raise DownloadError(
            "The cataloged artifact could not be downloaded.",
            remediation=_DOWNLOAD_REMEDIATION,
        )
    total = expected_size
    content_length = getattr(response, "headers", {}).get("Content-Length")
    if total is None and content_length:
        try:
            declared = int(content_length)
            total = declared + have if status == 206 else declared
        except ValueError:
            total = expected_size
    if progress is not None:
        progress(have, total)
    try:
        with part_path.open(mode) as handle:
            for chunk in response.iter_bytes():
                if not chunk:
                    continue
                handle.write(chunk)
                have += len(chunk)
                if progress is not None:
                    progress(have, total)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise DownloadError(
            "The cataloged artifact could not be written to the cache.",
            remediation="Ensure the cache directory is writable and retry ceia-aisdk model pull.",
        ) from exc


def _fsync_file(path: Path) -> None:
    """Flush file contents to disk.

    Args:
        path: File to fsync.

    Raises:
        DownloadError: If the file cannot be flushed.
    """
    try:
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
    except OSError as exc:
        raise DownloadError(
            "The cataloged artifact could not be flushed to disk.",
            remediation="Retry ceia-aisdk model pull on a filesystem that supports durable writes.",
        ) from exc
