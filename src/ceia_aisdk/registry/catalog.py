"""Catalog loading, schema validation, and versioned alias resolution.

The YAML parser is imported when this module is first used, not when
``import ceia_aisdk`` runs. Catalog origin URLs stay internal.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlparse

from ceia_aisdk._logging import get_logger
from ceia_aisdk.config import AISDKConfig
from ceia_aisdk.errors import DownloadError, ModelNotFoundError

_LOGGER = get_logger(__name__)
_CATALOG_ENV = "CEIA_AISDK_CATALOG"
_SCHEMA_VERSION = 1
_QUANTIZATION_CLASSES: Final[frozenset[str]] = frozenset({"compact", "standard", "high-quality"})
_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_ESSENTIAL_RE = re.compile(r"^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALIAS_RE = re.compile(
    r"^(?:(?P<domain>[a-z0-9][a-z0-9-]*)/)?(?P<size>[a-z0-9][a-z0-9-]*)"
    r"(?:@(?P<version>latest|[1-9][0-9]*))?$"
)
_ALLOWED_TOP_LEVEL = frozenset({"schema_version", "essentials", "models"})
_ALLOWED_SIZE_KEYS = frozenset({"latest", "versions"})
_ALLOWED_VERSION_KEYS = frozenset({"url", "sha256", "size_bytes", "public"})
_ALLOWED_PUBLIC_KEYS = frozenset(
    {
        "license_family",
        "commercial_use",
        "context_length",
        "size_gb",
        "capabilities",
        "quantization_class",
    }
)
_SCHEMA_REMEDIATION = (
    "Provide a catalog YAML document that matches schema_version 1 in the "
    "CEIA AI SDK catalog contract (schema_version, essentials, and models "
    "with a single http(s) URL, SHA-256, size_bytes, and public block per "
    "version)."
)


@dataclass(frozen=True, slots=True)
class PublicModelMetadata:
    """Disclosable metadata for a cataloged model alias.

    Attributes:
        license_family: License family label such as ``apache-2.0``.
        commercial_use: Whether the catalog marks commercial use as allowed.
        context_length: Positive context window length.
        size_gb: Approximate on-disk size in gigabytes.
        capabilities: Ordered capability labels such as ``chat``.
        quantization_class: One of ``compact``, ``standard``, or ``high-quality``.
    """

    license_family: str
    commercial_use: bool
    context_length: int
    size_gb: float
    capabilities: tuple[str, ...]
    quantization_class: str


@dataclass(frozen=True, slots=True)
class ResolvedAlias:
    """Stable catalog identity without origin fields.

    Attributes:
        alias: Canonical ``domain/size@N`` string.
        domain: Catalog domain such as ``llm``.
        size: Size token such as ``small``.
        version: Positive integer version pinned by the active catalog.
        public: Public metadata for the pin.
    """

    alias: str
    domain: str
    size: str
    version: int
    public: PublicModelMetadata

    def __repr__(self) -> str:
        """Return a representation that omits origin fields.

        Returns:
            A string containing only public identity fields.
        """
        return (
            "ResolvedAlias("
            f"alias={self.alias!r}, domain={self.domain!r}, "
            f"size={self.size!r}, version={self.version}, "
            f"public={self.public!r})"
        )


@dataclass(frozen=True, slots=True)
class CatalogVersion:
    """Internal pin for one cataloged artifact version.

    Attributes:
        url: Single download location. Not part of the public registry types.
        sha256: Lowercase hex SHA-256 of the artifact.
        size_bytes: Declared payload size.
        public: Public metadata block.
    """

    url: str
    sha256: str
    size_bytes: int
    public: PublicModelMetadata


@dataclass(frozen=True, slots=True)
class CatalogPin:
    """Latest pointer and version map for one domain/size pair.

    Attributes:
        latest: Positive version integer that exists in ``versions``.
        versions: Mapping of version number to internal pin.
    """

    latest: int
    versions: Mapping[int, CatalogVersion]


@dataclass(frozen=True, slots=True)
class CatalogDocument:
    """Validated in-memory catalog.

    Attributes:
        schema_version: Catalog schema version. Must be ``1``.
        essentials: Fully qualified aliases used by ``model pull --essentials``.
        models: Nested mapping of domain to size to pin.
    """

    schema_version: int
    essentials: tuple[str, ...]
    models: Mapping[str, Mapping[str, CatalogPin]]

    def pin(self, domain: str, size: str) -> CatalogPin:
        """Return the pin for a domain and size.

        Args:
            domain: Catalog domain such as ``llm``.
            size: Size token such as ``small``.

        Returns:
            The matching pin.

        Raises:
            KeyError: If the domain or size is absent.
        """
        return self.models[domain][size]


def resolve(
    alias: str,
    *,
    config: AISDKConfig | None = None,
    domain: str | None = None,
) -> ResolvedAlias:
    """Map a public alias to a catalog identity without downloading.

    Args:
        alias: Cataloged alias such as ``llm/small`` or ``llm/small@1``.
        config: Effective configuration. Catalog loading uses the process
            environment; cache files are not created.
        domain: Domain context for an unqualified size token such as
            ``small``. Programmatic callers must pass ``domain`` or a
            domain-qualified alias.

    Returns:
        The canonical resolved identity for the active catalog.

    Raises:
        ModelNotFoundError: If the alias is unqualified without a domain
            context, or is not present in the active catalog.
        DownloadError: If the active catalog cannot be loaded.
    """
    resolved, _entry = resolve_internal(alias, config=config, domain=domain)
    return resolved


def resolve_internal(
    alias: str,
    *,
    config: AISDKConfig | None = None,
    domain: str | None = None,
) -> tuple[ResolvedAlias, CatalogVersion]:
    """Resolve an alias and return the public identity plus internal pin.

    Args:
        alias: Cataloged alias token.
        config: Effective configuration passed to catalog loading.
        domain: Optional domain context for unqualified names.

    Returns:
        The public ``ResolvedAlias`` and the internal version pin.

    Raises:
        ModelNotFoundError: If the alias cannot be mapped.
        DownloadError: If the catalog cannot be loaded.
    """
    parsed_domain, parsed_size, parsed_version = parse_catalog_alias(alias, domain=domain)
    catalog = load_catalog(config=config)
    try:
        pin = catalog.pin(parsed_domain, parsed_size)
    except KeyError as exc:
        raise _unknown_alias(alias, parsed_domain, catalog) from exc
    if parsed_version == "latest":
        version_n = pin.latest
    else:
        version_n = parsed_version
        if version_n not in pin.versions:
            raise _unknown_alias(alias, parsed_domain, catalog)
    entry = pin.versions[version_n]
    resolved = ResolvedAlias(
        alias=f"{parsed_domain}/{parsed_size}@{version_n}",
        domain=parsed_domain,
        size=parsed_size,
        version=version_n,
        public=entry.public,
    )
    _LOGGER.debug("Resolved alias %s to %s", alias, resolved.alias)
    return resolved, entry


def parse_catalog_alias(
    alias: str,
    *,
    domain: str | None = None,
) -> tuple[str, str, int | str]:
    """Parse a cataloged alias token.

    Args:
        alias: Raw alias such as ``llm/small@latest`` or ``small``.
        domain: Domain context applied when the token has no domain.

    Returns:
        Domain, size, and either ``latest`` or a positive version integer.

    Raises:
        ModelNotFoundError: If the token is not a cataloged alias, or an
            unqualified name is used without a domain context.
    """
    if not isinstance(alias, str) or not alias.strip():
        raise ModelNotFoundError(
            "A nonempty catalog alias is required.",
            remediation="Use a domain-qualified alias such as llm/small.",
        )
    token = alias.strip()
    if ".." in token or "\\" in token or "\x00" in token:
        raise ModelNotFoundError(
            "The alias contains invalid path characters.",
            remediation="Use a domain-qualified alias such as llm/small.",
        )
    match = _ALIAS_RE.fullmatch(token)
    if match is None:
        raise ModelNotFoundError(
            "The alias is not a cataloged domain/size name.",
            remediation="Use a domain-qualified alias such as llm/small or llm/small@1.",
        )
    parsed_domain = match.group("domain")
    parsed_size = match.group("size")
    raw_version = match.group("version")
    if parsed_domain is None:
        if domain is None:
            raise ModelNotFoundError(
                "Programmatic registry calls require a domain-qualified alias.",
                remediation="Call resolve('llm/small') or pass domain='llm' for unqualified names.",
            )
        if not _TOKEN_RE.fullmatch(domain):
            raise ModelNotFoundError(
                "The domain context is not a valid catalog domain token.",
                remediation="Pass domain='llm' or use a domain-qualified alias such as llm/small.",
            )
        parsed_domain = domain
    version: int | str = "latest" if raw_version in {None, "latest"} else int(raw_version)
    return parsed_domain, parsed_size, version


def _unknown_alias(alias: str, domain: str, catalog: CatalogDocument) -> ModelNotFoundError:
    """Build a missing-alias error with same-domain suggestions.

    Args:
        alias: Original user token.
        domain: Parsed domain, if known.
        catalog: Active catalog used for suggestions.

    Returns:
        A ``ModelNotFoundError`` that does not include origin URLs.
    """
    names = []
    sizes = catalog.models.get(domain, {})
    for size in sizes:
        names.append(f"{domain}/{size}")
    if names:
        listed = ", ".join(names)
        remediation = f"Use one of: {listed}."
    else:
        remediation = "Use a domain-qualified alias such as llm/small."
    return ModelNotFoundError(
        f"Alias {alias} is not in the active catalog.",
        remediation=remediation,
    )


def parse_catalog_document(document: Mapping[str, Any] | str | bytes) -> CatalogDocument:
    """Parse and validate a catalog mapping or YAML text.

    Args:
        document: Mapping, YAML string, or YAML bytes.

    Returns:
        A validated catalog document.

    Raises:
        DownloadError: If the document is not valid YAML or fails the schema.
    """
    if isinstance(document, (str, bytes)):
        parsed = _parse_yaml(document)
    elif isinstance(document, Mapping):
        parsed = document
    else:
        raise _schema_error("The catalog document must be a mapping or YAML text.")
    return _validate_document(parsed)


def load_catalog(*, config: AISDKConfig | None = None) -> CatalogDocument:
    """Load the active catalog from an override or the bundled package data.

    Args:
        config: Effective configuration. Remote overrides honor ``offline``.

    Returns:
        The validated active catalog.

    Raises:
        DownloadError: If the catalog cannot be read or fails the schema.
    """
    override = os.environ.get(_CATALOG_ENV, "").strip()
    if override:
        return _load_override(override, config=config)
    return _load_bundled()


def get_public_metadata(
    alias: str,
    *,
    config: AISDKConfig | None = None,
    domain: str | None = None,
) -> PublicModelMetadata:
    """Return the public metadata block for a cataloged alias.

    Args:
        alias: Cataloged alias such as ``llm/small``.
        config: Effective configuration.
        domain: Domain context for an unqualified size token.

    Returns:
        Public fields only. Origin URL and checksum are omitted.

    Raises:
        ModelNotFoundError: If the alias is not in the active catalog.
        DownloadError: If the catalog cannot be loaded.
    """
    return resolve(alias, config=config, domain=domain).public


def _load_bundled() -> CatalogDocument:
    """Load the catalog shipped as package data.

    Returns:
        The bundled catalog document.

    Raises:
        DownloadError: If the bundled file is missing or invalid.
    """
    resource = files("ceia_aisdk.registry").joinpath("_internal_catalog.yaml")
    try:
        text = resource.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        raise DownloadError(
            "The bundled model catalog is missing from the installed package.",
            remediation=(
                "Reinstall ceia-aisdk from this repository so "
                "registry/_internal_catalog.yaml is included as package data."
            ),
        ) from exc
    return parse_catalog_document(text)


def _load_override(location: str, *, config: AISDKConfig | None = None) -> CatalogDocument:
    """Load a catalog from ``CEIA_AISDK_CATALOG``.

    Args:
        location: Local filesystem path or HTTP(S) URL.
        config: Effective configuration used to honor offline mode.

    Returns:
        The validated override catalog.

    Raises:
        DownloadError: If the location cannot be read or the schema fails.
    """
    if location.startswith(("http://", "https://")):
        return _load_remote_override(location, config=config)
    path = Path(location).expanduser()
    if not path.is_file():
        raise DownloadError(
            "The catalog override path is not a readable file.",
            remediation=(
                "Set CEIA_AISDK_CATALOG to an existing YAML file that matches "
                "schema_version 1, or unset the variable to use the bundled catalog."
            ),
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DownloadError(
            "The catalog override file is unreadable.",
            remediation=(
                "Fix permissions on the CEIA_AISDK_CATALOG file or unset the "
                "variable to use the bundled catalog."
            ),
        ) from exc
    _LOGGER.debug("Loaded catalog override from a local path")
    return parse_catalog_document(text)


def _load_remote_override(location: str, *, config: AISDKConfig | None = None) -> CatalogDocument:
    """Fetch an unsigned remote catalog override.

    Args:
        location: HTTP or HTTPS catalog URL.
        config: Effective configuration. Offline mode refuses the fetch.

    Returns:
        The validated remote catalog.

    Raises:
        DownloadError: If offline, the fetch fails, or the schema is invalid.
    """
    effective = config if config is not None else AISDKConfig.load()
    if effective.offline:
        raise DownloadError(
            "Refusing to fetch a remote catalog override while offline mode is enabled.",
            remediation=(
                "Unset CEIA_AISDK_OFFLINE or point CEIA_AISDK_CATALOG at a local "
                "YAML file that matches schema_version 1."
            ),
        )
    import httpx

    host = urlparse(location).hostname or "unknown-host"
    _LOGGER.debug("Fetching catalog override from host %s", host)
    try:
        timeout = httpx.Timeout(10.0, read=30.0)
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            response = client.get(location)
            response.raise_for_status()
            text = response.text
    except httpx.HTTPError as exc:
        _LOGGER.error("Remote catalog override fetch failed from host %s", host)
        raise DownloadError(
            "The remote catalog override could not be downloaded.",
            remediation=(
                "Set CEIA_AISDK_CATALOG to a reachable YAML document that matches "
                "schema_version 1, or unset the variable to use the bundled catalog."
            ),
        ) from exc
    return parse_catalog_document(text)


def _parse_yaml(document: str | bytes) -> Any:
    """Parse YAML text with ``SafeLoader``.

    Args:
        document: YAML string or bytes.

    Returns:
        The loaded object.

    Raises:
        DownloadError: If the text is not valid YAML.
    """
    import yaml

    try:
        loaded = yaml.safe_load(document)
    except yaml.YAMLError as exc:
        raise _schema_error("The catalog document is not valid YAML.") from exc
    return loaded


def _schema_error(message: str) -> DownloadError:
    """Return a schema failure that never includes origin URLs.

    Args:
        message: User-facing explanation without origin URLs.

    Returns:
        A ``DownloadError`` whose remediation names the catalog schema.
    """
    return DownloadError(message, remediation=_SCHEMA_REMEDIATION)


def _validate_document(raw: Any) -> CatalogDocument:
    """Validate a loaded catalog object against schema version 1.

    Args:
        raw: Object produced by YAML loading or a mapping.

    Returns:
        A validated catalog document.

    Raises:
        DownloadError: If any schema rule fails.
    """
    if not isinstance(raw, Mapping):
        raise _schema_error("The catalog document must be a YAML mapping.")
    extra = set(raw) - _ALLOWED_TOP_LEVEL
    if extra:
        raise _schema_error("The catalog document contains unsupported top-level fields.")
    if raw.get("schema_version") != _SCHEMA_VERSION:
        raise _schema_error("The catalog schema_version must be the integer 1.")
    essentials = _validate_essentials(raw.get("essentials"))
    models_raw = raw.get("models")
    if not isinstance(models_raw, Mapping) or not models_raw:
        raise _schema_error("The catalog models mapping is missing or empty.")
    models: dict[str, dict[str, CatalogPin]] = {}
    for domain, sizes in models_raw.items():
        if not isinstance(domain, str) or not _TOKEN_RE.fullmatch(domain):
            raise _schema_error("Catalog domain names must be lowercase tokens.")
        if not isinstance(sizes, Mapping) or not sizes:
            raise _schema_error("Each catalog domain must map size tokens to pins.")
        parsed_sizes: dict[str, CatalogPin] = {}
        for size, pin_raw in sizes.items():
            if not isinstance(size, str) or not _TOKEN_RE.fullmatch(size):
                raise _schema_error("Catalog size names must be lowercase tokens.")
            parsed_sizes[size] = _validate_pin(pin_raw)
        models[domain] = parsed_sizes
    return CatalogDocument(
        schema_version=_SCHEMA_VERSION,
        essentials=essentials,
        models=models,
    )


def _validate_essentials(raw: Any) -> tuple[str, ...]:
    """Validate the essentials list.

    Args:
        raw: Loaded essentials value.

    Returns:
        Fully qualified alias strings.

    Raises:
        DownloadError: If an entry is not ``domain/size``.
    """
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise _schema_error("Catalog essentials must be a list of alias strings.")
    essentials: list[str] = []
    for item in raw:
        if not _ESSENTIAL_RE.fullmatch(item):
            raise _schema_error(
                "Each essentials entry must be a fully qualified domain/size alias."
            )
        essentials.append(item)
    return tuple(essentials)


def _validate_pin(raw: Any) -> CatalogPin:
    """Validate one domain/size pin.

    Args:
        raw: Loaded pin mapping.

    Returns:
        A validated pin.

    Raises:
        DownloadError: If latest or versions are invalid.
    """
    if not isinstance(raw, Mapping):
        raise _schema_error("Each catalog size pin must be a mapping.")
    extra = set(raw) - _ALLOWED_SIZE_KEYS
    if extra:
        raise _schema_error("A catalog size pin contains unsupported fields.")
    latest = raw.get("latest")
    if not isinstance(latest, int) or isinstance(latest, bool) or latest < 1:
        raise _schema_error("Each size pin latest value must be a positive integer.")
    versions_raw = raw.get("versions")
    if not isinstance(versions_raw, Mapping) or not versions_raw:
        raise _schema_error("Each size pin must declare a versions mapping.")
    versions: dict[int, CatalogVersion] = {}
    for key, value in versions_raw.items():
        version = _coerce_version(key)
        versions[version] = _validate_version_entry(value)
    if latest not in versions:
        raise _schema_error("Each size pin latest version must exist under versions.")
    return CatalogPin(latest=latest, versions=versions)


def _coerce_version(key: Any) -> int:
    """Coerce a YAML version key to a positive integer.

    Args:
        key: Mapping key from YAML.

    Returns:
        The version number.

    Raises:
        DownloadError: If the key is not a positive integer without leading zeros.
    """
    if isinstance(key, bool) or not isinstance(key, int):
        if isinstance(key, str) and re.fullmatch(r"[1-9][0-9]*", key):
            return int(key)
        raise _schema_error("Catalog version keys must be positive integers.")
    if key < 1:
        raise _schema_error("Catalog version keys must be positive integers.")
    return key


def _validate_version_entry(raw: Any) -> CatalogVersion:
    """Validate one version entry.

    Args:
        raw: Loaded version mapping.

    Returns:
        A validated version entry.

    Raises:
        DownloadError: If required fields are missing or extra hosts are present.
    """
    if not isinstance(raw, Mapping):
        raise _schema_error("Each catalog version entry must be a mapping.")
    extra = set(raw) - _ALLOWED_VERSION_KEYS
    if extra:
        raise _schema_error(
            "Catalog version entries must not declare mirrors, signatures, or extra URLs."
        )
    url = raw.get("url")
    if not isinstance(url, str):
        raise _schema_error("Each catalog version must declare exactly one URL string.")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise _schema_error("Each catalog version URL must be an http or https location.")
    sha256 = raw.get("sha256")
    if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
        raise _schema_error(
            "Each catalog version sha256 must be 64 lowercase hexadecimal characters."
        )
    size_bytes = raw.get("size_bytes")
    if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 1:
        raise _schema_error("Each catalog version size_bytes must be a positive integer.")
    public = _validate_public(raw.get("public"))
    return CatalogVersion(url=url, sha256=sha256, size_bytes=size_bytes, public=public)


def _validate_public(raw: Any) -> PublicModelMetadata:
    """Validate the public metadata block.

    Args:
        raw: Loaded public mapping.

    Returns:
        Public metadata.

    Raises:
        DownloadError: If the public block is incomplete or invalid.
    """
    if not isinstance(raw, Mapping):
        raise _schema_error("Each catalog version must include a public metadata mapping.")
    extra = set(raw) - _ALLOWED_PUBLIC_KEYS
    if extra:
        raise _schema_error("The public metadata block contains unsupported fields.")
    missing = _ALLOWED_PUBLIC_KEYS - set(raw)
    if missing:
        raise _schema_error("The public metadata block is missing required fields.")
    license_family = raw["license_family"]
    if not isinstance(license_family, str) or not license_family.strip():
        raise _schema_error("public.license_family must be a nonempty string.")
    commercial_use = raw["commercial_use"]
    if not isinstance(commercial_use, bool):
        raise _schema_error("public.commercial_use must be a boolean.")
    context_length = raw["context_length"]
    if (
        not isinstance(context_length, int)
        or isinstance(context_length, bool)
        or context_length < 1
    ):
        raise _schema_error("public.context_length must be a positive integer.")
    size_gb = raw["size_gb"]
    if isinstance(size_gb, bool) or not isinstance(size_gb, (int, float)) or size_gb <= 0:
        raise _schema_error("public.size_gb must be a positive number.")
    capabilities = raw["capabilities"]
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or not all(isinstance(item, str) and item.strip() for item in capabilities)
    ):
        raise _schema_error("public.capabilities must be a nonempty list of strings.")
    quantization_class = raw["quantization_class"]
    if quantization_class not in _QUANTIZATION_CLASSES:
        raise _schema_error("public.quantization_class must be compact, standard, or high-quality.")
    return PublicModelMetadata(
        license_family=license_family,
        commercial_use=commercial_use,
        context_length=context_length,
        size_gb=float(size_gb),
        capabilities=tuple(capabilities),
        quantization_class=quantization_class,
    )
