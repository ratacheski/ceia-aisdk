# PRD 01 — Model registry and cache

| Field | Value |
|---|---|
| ID | `PRD-01` |
| Status | Draft |
| Speckit slug | `model-registry` |
| Depends on | PRD-00 |
| Unblocks | PRD 02–05 |
| PyPI | **Not published.** Installation continues from the repository. |
| Source plan | Stage 2 (MVP: no Ed25519, no official mirrors) |

---

### 1. Executive Summary

- **Problem Statement**: Without a versioned catalog, integrity-checked downloads, and a deterministic cache, first-chat depends on the user hunting for GGUF files online — the opposite of a PyPI product that competes with Ollama.
- **Proposed Solution**: An opaque registry with `domain/size@N` aliases, a catalog bundled in the wheel, an HTTP downloader with resume support + mandatory `sha256`, a cache at `~/.ceia-aisdk/models/`, and the `ceia-aisdk model *` CLI.
- **Success Criteria**:
  - `ceia-aisdk model pull llm/small` downloads the artifact, verifies `sha256`, and writes it to the cache at an opaque path; a rerun with a warm cache completes in ≤ 2 s and generates no HTTP GET request.
  - An interrupted download (kill -9 after ≥ 8 MB) resumes through Range, and the final file matches the catalog `sha256`.
  - A checksum mismatch discards the file and raises `DownloadError` with `.remediation`; nothing is promoted to the final path.
  - `model info` never prints the HF repository, upstream filename, or URL — only the `public` block.
  - `CEIA_AISDK_OFFLINE=1` + a cache miss fails in ≤ 100 ms with `DownloadError`, without attempting to open a socket.

---

### 2. User Experience & Functionality

- **User Personas**: hobbyist performing the first pull (still from a clone); script that pins `small@2`; company that points `CEIA_AISDK_CATALOG` to an internal YAML file.

- **User Stories**:

  **US-01-1 — Resolve an alias**
  - As a developer, I want to request `llm/small` or `small` so that I do not have to memorize the actual artifact.
  - **Acceptance Criteria**:
    - Accepted forms: `llm/small`, `small` (the domain is implicit only when the caller declares it — the public registry API requires a domain or a context), `llm/small@3`, `llm/small@latest`.
    - `@latest` is pinned by the installed SDK version; there is no silent remote refresh.
    - Unknown alias → `ModelNotFoundError` + a list of aliases in the same domain.
    - `hf://...` and a local path are documented bypasses; the SDK does not rewrite the filename in the opaque cache (it stores it as custom, with metadata `source=bypass`).

  **US-01-2 — Download with integrity**
  - As a developer, I want to pull an alias with a progress bar so that I can trust the binary.
  - **Acceptance Criteria**:
    - CLI: `pull`, `list`, `rm`, `info`, `verify`, `where`.
    - HTTP with resume support, Rich progress, and mandatory `sha256` in the catalog.
    - One URL per artifact in this PRD (HF organization `ceia-aisdk` or a test stub URL). **No mirror list and no multi-host failover.**
    - `model verify` rehashes the cache against the catalog; exits with code ≠ 0 on a mismatch.
    - `model where` prints the absolute cache path.

  **US-01-3 — View public metadata**
  - As a commercial developer, I want to see the license family and `commercial_use` so that I can make my own decision.
  - **Acceptance Criteria**:
    - Public fields: `license_family`, `commercial_use`, `context_length`, `size_gb`, `capabilities`, `quantization_class`.
    - `info` and the `get_public_metadata(alias)` API return only these fields.
    - There is **no** `LicenseError`. The SDK does not block pull or load operations based on the license.

  **US-01-4 — Opaque, concurrent cache**
  - As a developer, I want two processes to avoid corrupting the same pull so that CI and an application can compete for it safely.
  - **Acceptance Criteria**:
    - Layout `~/.ceia-aisdk/models/<domain>/<opaque-alias>.bin` (the name does not contain the upstream repository string).
    - One lockfile per artifact; the second process waits or reuses the result.
    - `rm` deletes the file + lock; `list` shows cached aliases and their sizes.

  **US-01-5 — Private catalog / air gap**
  - As an operator, I want to point `CEIA_AISDK_CATALOG` to a catalog so that downloads do not depend on the public organization.
  - **Acceptance Criteria**:
    - Accepts a local path or an HTTP URL for a YAML file using the same schema.
    - No signature verification in this PRD (signatures are a Non-Goal).
    - Invalid schema → `AISDKError`/`DownloadError` with remediation referencing the schema.

- **Non-Goals**:
  - `catalog.yaml.sig`, Ed25519, `CatalogSignatureError`, `CEIA_AISDK_ALLOW_UNSIGNED_CATALOG`.
  - Official mirrors and failover between hosts. A failing URL = `DownloadError`.
  - Inference and device selection based on VRAM versus `size_gb` (that rule enters in PRD 02 using the `size_gb` defined here).
  - Torrent, a proprietary CDN, upload to PyPI, `bundle create`, or desktop packaging.
  - Publishing the HF organization (the development catalog may point to local HTTP fixtures).

  **P1 (part of this PRD, not distribution):** `model pull --essentials` downloads the essential aliases already present in the catalog (`llm/small` at minimum); missing ones generate a warning, not a crash. It only warms `~/.ceia-aisdk/models/`.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**: HTTP client with Range support (httpx or an equivalent already justified in the Speckit plan). No GPU. Fixtures: a file ≥ 16 MB with a known `sha256` in the integration suite.
- **Evaluation Strategy**:
  - Resolver tests (`@N`, `@latest`, miss).
  - Resume test with a local HTTP server that counts requests.
  - Tampering test: modify 1 byte in the cache → `verify` fails; `pull` redownloads or refuses to promote the file.
  - Opacity test: snapshots of `info` and `str(exception)` without `huggingface.co` substrings / production repository names.
  - Offline test.

---

### 4. Technical Specifications

- **Architecture Overview**:
  - `ceia_aisdk/registry/{catalog,downloader,cache}.py`. No `signing.py`.
  - Bundled catalog: `ceia_aisdk/registry/_internal_catalog.yaml` (underscore = not an API).
  - Resolver: alias → internal entry `{url, sha256, size, public}`.
  - Downloader: tmp + fsync + atomic rename after a successful hash check.
- **Integration Points**:
  - Consumes `AISDKConfig.cache_dir` and `.offline`.
  - Exposes a stable internal API for PRD 02: `resolve()`, `ensure_local(alias) -> Path`, `public_info(alias)`.
  - Typer CLI subapp `model`.
- **Security & Privacy**:
  - Integrity = artifact `sha256`. No authenticity verification for the remote *catalog* (an accepted risk in this increment; document it in `model info --help` and troubleshooting).
  - Do not log the internal URL at WARNING/ERROR level without the debug flag. DEBUG may log the host, but not the full repository path when avoidable — at minimum, `info` remains opaque.
  - Path traversal: sanitize aliases and cache destinations; a local `CEIA_AISDK_CATALOG` cannot cause the downloader to write outside `cache_dir` / the cache tmp directory.

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **This PRD**: bundled catalog + 1 URL + sha256 + CLI + cache + `hf://` and local path bypasses.
  - **P1 in this PRD**: `model pull --essentials` (only aliases that are present).
  - **Publish**: not yet. The public wheel is introduced in PRD 02 and already includes this registry.
  - **Outside this series**: Ed25519, mirrors, [desktop packaging](08-packaging.md).
- **Technical Risks**:
  - The `ceia-aisdk` HF organization may not exist at implementation time. Mitigation: HTTP fixture in CI; inject the real URL when the organization is ready. PRD 02 cannot depend on an unavailable production weight — it requires a test artifact.
  - Opacity versus debugging: the plan accepts this trade-off; the `hf://` bypass is the escape hatch.
  - An unsigned remote catalog is a MITM vector. Mitigation: default = bundled; the documentation makes the risk explicit until signing is available.

**Challenge to the plan:** signing and mirrors in the same registry increment delay first-chat and do not improve the 15-minute KPI. Checksum + bundled is the minimum honest contract.

**Speckit:** feature `model-registry`. The spec must list the CLI commands and the `ensure_local()` contract.
