# Research: Model Registry and Cache

**Feature**: `002-model-registry`
**Date**: 2026-09-01

## 1. HTTP Client and Resume

**Decision**: Use `httpx` as a runtime dependency, imported only by the downloader. Stream
cataloged artifacts with HTTP `Range` so an interrupted `.part` file can continue. Apply a
connect timeout and a read timeout. Follow redirects. Treat any network error, HTTP 4xx/5xx
(except a completed 206 resume), timeout, or closed connection as a hard `DownloadError`. Do not
retry a second host.

**Rationale**: PRD-01 requires resumable downloads and names `httpx` as the expected client.
Streaming avoids holding multi-gigabyte files in memory. Lazy import preserves the foundation
import budget: `import ceia_aisdk` must not load `httpx`.

**Alternatives considered**:

- `urllib.request`: supports `Range` without a dependency, but timeout, streaming, and redirect
  handling are more error-prone and would duplicate code `httpx` already provides.
- `requests`: mature, but `httpx` is the current default for new Python HTTP clients and matches
  the PRD.
- Mirror failover: rejected by the specification.

**Risks and validation**:

- Integration tests must serve a fixture of at least 16 MiB from a local HTTP server that counts
  GET requests and honors `Range`.
- Warm-cache pulls must record zero HTTP requests.
- A kill after ≥ 8 MiB must produce a second GET with `Range` and a final SHA-256 match.

## 2. Catalog Format and Bundling

**Decision**: Ship one YAML catalog as package data at
`ceia_aisdk/registry/_internal_catalog.yaml`. Parse with PyYAML `SafeLoader` only. The file is
not a public module. `schema_version: 1` is required. Nested keys are `models.<domain>.<size>`
with `latest: <int>` and `versions.<N>` entries. Each version declares exactly one `url`, a
64-character lowercase hex `sha256`, `size_bytes`, and a `public` block. A top-level
`essentials` list names fully qualified aliases; `llm/small` must appear in the bundled catalog.

`CEIA_AISDK_CATALOG` overrides the bundled file. A local path or `http://` / `https://` URL is
accepted. The override is not an `AISDKConfig` field and has no TOML key in this feature.
Invalid schema raises `DownloadError` with remediation that names the schema. No signature is
verified.

The committed bundled catalog pins production aliases `llm/small@1`, `llm/medium@1`, and
`llm/large@1` to the opaque files published on 2026-09-01 under the Hugging Face organization
`ceia-aisdk` (`llm-small-v1`, `llm-medium-v1`, `llm-large-v1`, each as `model.gguf`). Tests
inject a local catalog via `CEIA_AISDK_CATALOG` and never download those production weights.

**Rationale**: YAML is the operator contract in PRD-01. Nesting `latest` inside each size pin
`@latest` to the installed file, so there is no remote refresh. Package data keeps the catalog
inside the wheel without embedding weights. Leaving the override out of `AISDKConfig` avoids
changing the foundation field set.

**Alternatives considered**:

- JSON catalog: avoids PyYAML, but operators were promised YAML.
- TOML catalog: consistent with `config.toml`, but diverges from the PRD schema.
- Encoding `@N` only in map keys: harder to pin `@latest` explicitly.
- Adding `catalog` to `AISDKConfig`: deferred; the specification names only the environment
  variable.

**Risks and validation**:

- Wheel inspection must include the YAML file and must reject GGUF/bin weight files.
- Schema tests cover missing fields, extra hosts, uppercase hashes, non-hex hashes, and
  traversal in URLs that become cache destinations.
- A remote catalog override is a MITM risk; help and troubleshooting must state that authenticity
  is not verified.

## 3. Cache Layout, Locks, and Atomic Promotion

**Decision**: Store cataloged artifacts at:

```text
<cache_dir>/models/<domain>/<size>-v<N>.bin
<cache_dir>/models/<domain>/<size>-v<N>.meta.json
<cache_dir>/models/<domain>/<size>-v<N>.lock
<cache_dir>/models/.tmp/<domain>-<size>-v<N>.part
```

The opaque basename is derived only from the public alias (`small-v1.bin`), never from an
upstream repository or filename. Sidecar JSON records `alias`, `source` (`catalog` or
`bypass`), `sha256` when known, and `size_bytes`. Bypass files live under `models/custom/` and
keep a sanitized original basename.

Create `models/` and `.tmp/` as needed. Download into the `.part` file, `fsync`, hash, then
`os.replace` onto the final `.bin`. A failed hash deletes the candidate and does not leave a
final `.bin`. Resume appends to the existing `.part` using `Range`.

Concurrency uses one `fcntl.flock` exclusive lock per artifact on Linux. The second process
blocks until the first releases the lock, then reuses a valid `.bin` or retries/fails without
mixing writers. A crashed holder releases the lock automatically. If flock is unsupported, raise
`DownloadError` with remediation. Do not busy-spin forever on a userspace pid file.

**Rationale**: Atomic replace is the standard way to make a file appear only after it is
complete. `fcntl.flock` matches the Linux-only constitution and recovers from `kill -9` without
stale-pid logic. Sidecars let `list`, `verify`, and `where` recover alias metadata from opaque
names.

**Alternatives considered**:

- `filelock` / `portalocker`: useful for Windows, which is out of scope.
- Encoding the upstream filename in the cache: rejected by opacity.
- Hard-linking local bypasses without copying: rejected because removing the source would break
  later `ensure_local` calls.

**Risks and validation**:

- Concurrent-pull tests must start two processes against an empty cache and assert one valid
  file.
- Path-traversal tests must reject `..`, absolute aliases, and catalog URLs that resolve outside
  `cache_dir` / `.tmp`.
- Warm `ensure_local` must hash or trust a sidecar plus size and finish within 2 seconds without
  HTTP.

## 4. Public Registry Surface and Import Budget

**Decision**: Add `ceia_aisdk.registry` as the public programmatic module. Export
`resolve`, `ensure_local`, `get_public_metadata`, and `PublicModelMetadata`. Do not import that
module from `ceia_aisdk.__init__`. Re-export only the new error types `ModelNotFoundError` and
`DownloadError` from the package root, defined in `ceia_aisdk.errors`.

`resolve` returns a public identity (canonical alias, integer version, public metadata) and must
not include URL, SHA-256, or upstream names. Internal catalog objects stay private.
`ensure_local` returns a `pathlib.Path` to a verified local file, downloading when needed.
`get_public_metadata` returns the six public fields only.

Programmatic calls require a domain-qualified alias or an explicit `domain=` context.
Unqualified `small` is rejected there. The CLI supplies `domain="llm"` for unqualified names.

`httpx` is imported only inside the downloader. PyYAML is imported by the catalog loader when
the registry module is first used, not when `import ceia_aisdk` runs.

**Rationale**: The specification requires `ensure_local` for PRD-02 without forcing every
`import ceia_aisdk` to pay YAML/HTTP cost. Keeping URLs off the public resolve object preserves
opacity even for `repr()` of return values.

**Alternatives considered**:

- Re-exporting `ensure_local` from `__init__.py`: rejected because it would import the registry
  (and PyYAML) on every package import.
- Returning the internal catalog entry from `resolve`: rejected because it leaks URL and hash.
- A `public_info` alias: the specification chose `get_public_metadata`.

**Risks and validation**:

- Fresh-process import tests must add `httpx` and `yaml` to the forbidden loaded-module set for
  `import ceia_aisdk`.
- Downstream modules in later features import `ceia_aisdk.registry`, not CLI parsers.

## 5. CLI Subapp and Progress

**Decision**: Add a Typer sub-application `model` with commands `pull`, `list`, `rm`, `info`,
`verify`, and `where`. Keep Typer/Rich imports in CLI modules. Show a Rich progress bar only for
CLI downloads when stderr is a TTY; redirected or non-interactive output still completes and
prints a simple English line. Library `ensure_local` has no progress bar by default.

Exit codes: `0` success (including `verify` on an empty cache); `1` for `AISDKError` subclasses;
`2` for usage errors reserved by Typer. `verify` exits `1` on checksum mismatch.

**Rationale**: Matches the foundation CLI split (semantics vs rendering) and the specification's
command list. Progress is a user-facing pull requirement, not a library requirement.

**Alternatives considered**:

- Progress in `ensure_local` by default: noisy inside services and CI.
- A single `model` command with subparsers outside Typer: rejected because the foundation
  already uses Typer.

## 6. Offline Mode, Logging, and Opacity

**Decision**: Honor `AISDKConfig.offline`. On a cache miss, fail in ≤ 100 ms with
`DownloadError` before creating a client or opening a socket. A valid cached file is reused
offline. A corrupt cached cataloged file is not reused; online it is deleted and re-downloaded,
offline it is `DownloadError`.

Public `info` output, `get_public_metadata`, `str(exception)`, and `WARNING`/`ERROR` logs must
not contain the download URL, upstream repository, or upstream filename. `DEBUG` may log the
host only. Cataloged `model info` prints only the public block plus the alias/version identity.

Do not define `LicenseError` or `CatalogSignatureError`. License fields never block pull.

**Rationale**: PRD-00 stored `offline` without enforcing it; this feature is the download
boundary. Opacity is a product requirement, not a debug convenience.

**Alternatives considered**:

- Blocking DNS at the process level for offline: unnecessary if the client is never
  constructed.
- Logging full URLs at ERROR for support: rejected; remediation can mention `model where`,
  `CEIA_AISDK_CATALOG`, and debug logging instead.

## 7. Bypasses

**Decision**: Accept `hf://<repo>/<file>` and an existing local filesystem path as `ensure_local`
/ `model pull` inputs. Store them under `models/custom/` with sidecar `source=bypass`. Do not
rewrite to `<size>-v<N>.bin`. Do not apply a catalog SHA-256. A missing local path or failed
`hf://` fetch is `DownloadError`, not `ModelNotFoundError`. Cataloged `info` remains opaque.

**Rationale**: The specification names these as the opacity escape hatch and states that
bypasses do not use a catalog checksum.

**Alternatives considered**:

- Resolving `hf://` through the catalog: rejected; it is a bypass.
- Refusing bypasses until signing exists: rejected; developers need an escape hatch now.

## 8. Testing and Fixtures

**Decision**: Generate a ≥ 16 MiB fixture in the test temporary directory with a known SHA-256.
Serve it with a stdlib `http.server` subclass that counts requests and implements `Range`. Do
not commit weight files. Mark tests that need the loopback server with
`pytest.mark.enable_socket`; keep the default `--disable-socket` for the rest of the suite.

Add `httpx` and `pyyaml` as runtime dependencies via `uv add`. Do not add `pytest-httpserver`.
Extend contract tests for help, errors, opacity substrings, and package contents.

**Rationale**: A generated fixture keeps the repository small. A stdlib server gives exact
control over `Range` and request counts without another development dependency.

**Alternatives considered**:

- Committing a 16 MiB file: rejected because of repository size.
- Hitting the public host in CI: rejected because production weights are multi-gigabyte and
  would make the suite slow, flaky, and bandwidth-heavy. The organization exists; tests still
  use loopback fixtures.

## 9. Packaging and Documentation

**Decision**: Include `_internal_catalog.yaml` as package data. Keep the 5 MiB package-size
budget exclusive of declared dependencies. Do not publish to PyPI. Update the README and
`model info --help` with alias forms, commands, `ensure_local`, opacity, bypasses,
`CEIA_AISDK_CATALOG`, offline behavior, and the unsigned-catalog risk. All new text is English.

**Rationale**: Constitution I forbids embedding runtime weights. Constitution V requires
complete command help and examples.

**Alternatives considered**:

- Deferring documentation to PRD-02: rejected; each PRD includes its documentation increment.
