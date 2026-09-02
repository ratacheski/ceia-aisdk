# Data Model: Model Registry and Cache

**Feature**: `002-model-registry`
**Date**: 2026-09-01

This feature has no database. Persistent state is a local model cache plus an optional operator
catalog override. In-memory objects are immutable after validation.

## 1. Model Alias

### Purpose

Names a cataloged artifact without exposing the upstream file.

### Fields

- `raw: str`
  - User-supplied token: `llm/small`, `llm/small@3`, `llm/small@latest`, CLI `small`,
    `hf://...`, or a filesystem path.
- `kind: AliasKind`
  - `cataloged`, `hf_bypass`, or `path_bypass`.
- `domain: str | None`
  - Required for cataloged programmatic calls unless `domain=` context is supplied.
  - CLI unqualified names receive `llm`.
- `size: str | None`
  - Catalog size token such as `small`.
- `version: int | Literal["latest"] | None`
  - Absent version means `@latest` for cataloged aliases.

### Validation

- Cataloged domain and size match `^[a-z0-9][a-z0-9-]*$`.
- Version `N` is a positive integer without leading zeros.
- The token must not contain NUL, `..`, backslashes, or an absolute catalog path used as a
  domain/size.
- Programmatic cataloged aliases without domain or context are invalid.

### Failures

Unknown cataloged aliases after parsing raise `ModelNotFoundError` with same-domain suggestions.
Malformed bypasses and missing local files raise `DownloadError`.

## 2. Public Model Metadata

### Purpose

Discloses the information a commercial user needs without revealing the artifact origin.

### Public representation

`PublicModelMetadata` is an immutable, slotted value object.

### Fields

- `license_family: str`
- `commercial_use: bool`
- `context_length: int`
  - Positive.
- `size_gb: float`
  - Positive approximate on-disk size in gigabytes.
- `capabilities: tuple[str, ...]`
  - Ordered, nonempty strings such as `chat`.
- `quantization_class: str`
  - One of `compact`, `standard`, `high-quality`.

No other fields are public. URL, SHA-256, upstream repository, and upstream filename are absent.

## 3. Catalog Document

### Purpose

Pins every alias for the installed SDK version (or an operator override) to one download
location and checksum.

### Fields

- `schema_version: int`
  - Must equal `1`.
- `essentials: tuple[str, ...]`
  - Fully qualified aliases such as `llm/small`.
  - Missing names produce a warning during `--essentials`, not a crash.
- `models: mapping`
  - `models[domain][size].latest: int`
  - `models[domain][size].versions[N]: VersionEntry`

### Version entry (internal)

- `url: str`
  - Exactly one `http://` or `https://` location.
- `sha256: str`
  - 64 lowercase hexadecimal characters.
- `size_bytes: int`
  - Positive.
- `public: PublicModelMetadata`

### Invariants

- `@latest` for a size is exactly `versions[latest]` in the same document.
- The same installed catalog always resolves `llm/small` and `llm/small@latest` to the same `N`.
- There is no second URL, mirror list, or signature field.
- The bundled document is package data, not a public Python API.
- An override replaces the bundled document entirely; there is no merge and no fallback to a
  public organization.

### Load failures

Unreadable files, HTTP catalog-fetch failures, and schema violations raise `DownloadError` with
remediation that points at the schema. Offline mode must not fetch a remote catalog override.

## 4. Resolved Alias

### Purpose

Stable identity returned by `resolve` to later modules without downloading and without leaking
origin.

### Public fields

- `alias: str`
  - Canonical `domain/size@N`.
- `domain: str`
- `size: str`
- `version: int`
- `public: PublicModelMetadata`

Internal resolution may also carry URL, SHA-256, and size bytes, but those fields are not part
of the public object or its `repr`.

## 5. Cached Artifact

### Purpose

A local file that `ensure_local` can return.

### Layout

Cataloged:

- `bin`: `<cache_dir>/models/<domain>/<size>-v<N>.bin`
- `meta`: `<cache_dir>/models/<domain>/<size>-v<N>.meta.json`
- `lock`: `<cache_dir>/models/<domain>/<size>-v<N>.lock`
- `part`: `<cache_dir>/models/.tmp/<domain>-<size>-v<N>.part`

Bypass:

- `bin`: `<cache_dir>/models/custom/<sanitized-basename>`
- matching `.meta.json` and `.lock`

### Sidecar fields

- `alias: str | None`
- `source: str`
  - `catalog` or `bypass`
- `sha256: str | None`
  - Required for `catalog`; optional for `bypass`
- `size_bytes: int`

### States

- `absent`: no final `.bin`
- `partial`: `.part` exists; resume is allowed
- `valid`: `.bin` exists and cataloged SHA-256 matches
- `corrupt`: `.bin` exists but hash mismatches
- `bypassed`: `.bin` exists with `source=bypass`

### Invariants

- A cataloged `.bin` is visible only after a matching hash.
- Filenames contain no upstream repository, upstream filename, or URL.
- `rm` deletes `.bin`, sidecar, lock, and leftover `.part` for that artifact.
- Destinations always resolve inside `cache_dir/models` or `cache_dir/models/.tmp`.

## 6. Download Job

### Purpose

One attempt to produce a valid cached artifact.

### Fields

- `resolved: ResolvedAlias` or bypass source
- `destination: Path`
- `partial: Path`
- `bytes_have: int`
- `bytes_expected: int | None`
- `request_count: int`
  - Observed by tests; not a public API

### Rules

- Offline + `absent` or `corrupt` → `DownloadError` in ≤ 100 ms, no socket.
- Online + `valid` → return destination, no HTTP GET.
- Online + `partial` → `Range` from `bytes_have`.
- Online + `corrupt` → delete `.bin` and download again.
- Checksum mismatch after transfer → delete candidate, `DownloadError`, no final `.bin`.
- Single URL failure → `DownloadError`; no failover.

## 7. Artifact Lock

### Purpose

Serialize concurrent writers for one destination.

### Fields

- `path: Path`
  - Sibling `.lock` file
- `mode: exclusive flock`

### Transitions

```text
unlocked
  -> acquire exclusive
  -> inspect cache
  -> reuse valid bin or download/replace
  -> release (including process death)
```

A second process waits, then observes the winner's result. Mixed or truncated finals are
invalid states.

## 8. Public Registry Errors

### Hierarchy

- `AISDKError` (existing root)
- `ModelNotFoundError`
  - Alias is not in the active catalog.
  - Remediation lists aliases in the same domain when any exist.
- `DownloadError`
  - Transfer, integrity, catalog load/schema, offline miss, lock, or bypass I/O failure.
  - Remediation is nonempty and must not include the internal URL.

`LicenseError` and `CatalogSignatureError` are not defined.

### Opacity

`str(error)` and `.remediation` contain no `huggingface.co` production repository, upstream
filename, or catalog URL for cataloged operations.

## State Transitions

### Resolve

```text
raw alias
  -> bypass kind -> bypass source (no catalog pin)
  -> cataloged parse
  -> load active catalog
  -> unknown -> ModelNotFoundError
  -> pin @latest or @N -> ResolvedAlias
```

### Ensure local

```text
resolve
  -> acquire lock
  -> valid cached cataloged file -> return path
  -> offline miss/corrupt -> DownloadError
  -> download/resume into .part
  -> hash ok -> fsync and replace -> sidecar -> return path
  -> hash fail -> delete candidate -> DownloadError
```

### Verify

```text
scan cached cataloged artifacts
  -> empty cache -> success
  -> all hashes match -> success
  -> any mismatch -> nonzero exit, no promotion of corrupt files
```
