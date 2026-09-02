# Python API Contract: Model Registry

**Feature**: `002-model-registry`
**Stability**: Public contract for PRD-01, consumed by PRD-02+

This contract extends [001-sdk-foundations/contracts/python-api.md](../../001-sdk-foundations/contracts/python-api.md).
Foundation import, configuration, hardware, and `doctor` contracts remain in force.

## Package Root

`ceia_aisdk.__init__` additionally exports `ModelNotFoundError` and `DownloadError`.

It must not import `ceia_aisdk.registry`, `ceia_aisdk.cli`, `httpx`, `yaml`, Typer, Rich, or
inference backends.

`import ceia_aisdk` still finishes within the p95 200 ms reference target and makes no network
call.

## Errors

### `ModelNotFoundError`

Direct subclass of `AISDKError`. Raised when a cataloged alias is not in the active catalog.

- `.remediation` is nonempty English text.
- When the domain is known, remediation lists aliases in that domain.
- String conversion does not include catalog URLs or upstream names.

### `DownloadError`

Direct subclass of `AISDKError`. Raised for transfer, integrity, catalog load/schema, offline
miss, lock, path, and bypass I/O failures.

- `.remediation` is nonempty English text and may mention `CEIA_AISDK_OFFLINE`,
  `CEIA_AISDK_CATALOG`, `model verify`, or a local cache path.
- String conversion does not include the internal download URL.

`LicenseError` and `CatalogSignatureError` must not exist.

## Registry Module

Public module: `ceia_aisdk.registry`.

```python
def resolve(
    alias: str,
    *,
    config: AISDKConfig | None = None,
    domain: str | None = None,
) -> ResolvedAlias: ...

def ensure_local(
    alias: str,
    *,
    config: AISDKConfig | None = None,
    domain: str | None = None,
) -> Path: ...

def get_public_metadata(
    alias: str,
    *,
    config: AISDKConfig | None = None,
    domain: str | None = None,
) -> PublicModelMetadata: ...
```

`config` defaults to `AISDKConfig.load()`. Cache writes use `config.cache_dir`. Offline
enforcement uses `config.offline`.

### `resolve`

- Does not download and does not create cache files.
- Accepts `llm/small`, `llm/small@N`, and `llm/small@latest`.
- Unqualified `small` is rejected unless `domain` is supplied (`domain="llm"` yields
  `llm/small`).
- `@latest` is pinned by the active catalog document of the installed SDK (or override); no
  remote catalog refresh occurs.
- Returns `ResolvedAlias` with canonical `domain/size@N`, integer `version`, and
  `PublicModelMetadata`.
- `repr(ResolvedAlias)` and public attributes exclude URL, SHA-256, repository, and upstream
  filename.
- Unknown aliases raise `ModelNotFoundError`.

### `ensure_local`

- Returns a `pathlib.Path` to a local file that later modules may open.
- For cataloged aliases, the file exists at the opaque cache path and matches the catalog
  SHA-256.
- Downloads and verifies when the file is absent or corrupt and `config.offline` is false.
- When `config.offline` is true and the file is not valid, raises `DownloadError` within 100 ms
  without opening a socket.
- Warm valid cache returns within 2 seconds on reference local storage with zero HTTP GET
  requests.
- Accepts documented bypasses `hf://...` and an existing local filesystem path; those are stored
  as custom entries with sidecar `source=bypass`.
- Does not refuse based on license metadata.
- Concurrent callers serialize per artifact and never produce a mixed file.

### `get_public_metadata`

- Returns only `license_family`, `commercial_use`, `context_length`, `size_gb`,
  `capabilities`, and `quantization_class`.
- Does not download.
- Does not include URL or origin fields.

## Public Types

```python
@dataclass(frozen=True, slots=True)
class PublicModelMetadata:
    license_family: str
    commercial_use: bool
    context_length: int
    size_gb: float
    capabilities: tuple[str, ...]
    quantization_class: str

@dataclass(frozen=True, slots=True)
class ResolvedAlias:
    alias: str
    domain: str
    size: str
    version: int
    public: PublicModelMetadata
```

## Logging

- Registry modules use `logging.getLogger(__name__)`.
- `WARNING` and `ERROR` records must not contain the internal download URL.
- `DEBUG` may log the host, not the full repository path when avoidable.

## Documentation

Every public module, class, function, and method has an English docstring covering parameters,
returns, raised exceptions, and side effects (cache writes, network, locks).
