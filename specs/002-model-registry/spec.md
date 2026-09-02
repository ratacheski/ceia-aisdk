# Feature Specification: Model Registry and Cache

**Feature Branch**: `main` (no branch was created; there is no `before_specify` hook)

**Created**: 2026-09-01

**Status**: Draft

**Input**: PRD-01 (`docs/prd/01-model-registry.md`) and decisions ratified in the PRD program on 2026-09-01

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resolve a Versioned Alias (Priority: P1)

As a developer, I want to request a model by a stable alias such as `llm/small` or `llm/small@2` so that I do not have to hunt for, memorize, or depend on the real upstream artifact name.

**Why this priority**: Every later download, cache, and inference module depends on a deterministic mapping from a public alias to a single cataloged artifact for the installed SDK version.

**Independent Test**: Resolve known aliases (`llm/small`, `llm/small@N`, `llm/small@latest`), an unqualified name in CLI context, and an unknown alias, without downloading any file; confirm the pinned identity and the failure type.

**Acceptance Scenarios**:

1. **Given** the bundled catalog of the installed SDK, **When** a developer requests `llm/small`, `llm/small@<N>`, or `llm/small@latest`, **Then** the request resolves to a single cataloged artifact whose identity does not change for that installed SDK version.
2. **Given** the `ceia-aisdk model` command context, **When** a developer requests the unqualified name `small`, **Then** it resolves as `llm/small` for the installed SDK version.
3. **Given** a programmatic registry call without a domain or domain context, **When** the caller passes only `small`, **Then** the call is rejected; the public registry surface requires a domain-qualified alias or an explicit domain context.
4. **Given** an alias that is not in the active catalog, **When** resolution is attempted, **Then** the developer receives `ModelNotFoundError` with nonempty remediation and a list of aliases in the same domain.
5. **Given** `@latest` for an alias, **When** the same installed SDK version is used twice, **Then** both resolutions pin the same artifact; there is no silent remote catalog refresh.

---

### User Story 2 - Download with Integrity (Priority: P1)

As a developer, I want to pull an alias with visible progress and a verified checksum so that I can trust the binary that lands in the cache and retry safely after an interruption.

**Why this priority**: First-chat and every later module fail if the developer cannot obtain a trustworthy local copy without searching for files online.

**Independent Test**: Pull a cataloged test artifact into an empty cache, interrupt after at least 8 MB and resume, tamper with one byte, and run `verify` and `where` without depending on inference.

**Acceptance Scenarios**:

1. **Given** a cataloged alias and a working network, **When** the developer runs `ceia-aisdk model pull <alias>`, **Then** the artifact is downloaded with progress indication, checked against the catalog checksum, and stored only at its final cache location after the check succeeds.
2. **Given** a download interrupted after at least 8 MB have been transferred, **When** the developer pulls the same alias again, **Then** the transfer continues from the already received bytes, and the completed file matches the catalog checksum.
3. **Given** a completed file whose checksum does not match the catalog, **When** promotion to the final cache location is considered, **Then** the file is discarded, `DownloadError` is raised with nonempty remediation, and nothing is left at the final path.
4. **Given** a warm cache for that alias, **When** the developer pulls it again, **Then** the operation completes in 2 seconds or less and does not start a network download.
5. **Given** a cached alias, **When** the developer runs `ceia-aisdk model where <alias>`, **Then** the command prints the absolute cache path.
6. **Given** cached artifacts, **When** the developer runs `ceia-aisdk model verify`, **Then** each cached cataloged file is rehashed against the catalog; a mismatch exits with a nonzero code.
7. **Given** `CEIA_AISDK_OFFLINE` enabled and a cache miss, **When** pull or `ensure_local` is attempted, **Then** the failure is a `DownloadError` with nonempty remediation, occurs within 100 ms, and does not attempt to open a network connection.

---

### User Story 3 - Keep the Cache Opaque and Concurrent (Priority: P1)

As a developer, I want two processes to compete for the same pull without corrupting the file, and I want cache names that do not leak the upstream repository, so that CI and an application can share the cache safely.

**Why this priority**: A corrupt or leaky cache would make the registry unusable as the shared foundation for later modules and for commercial users who must not depend on upstream filenames.

**Independent Test**: Inspect cache paths and `model info` output for upstream identity; run two concurrent pulls of the same alias; list and remove a cached alias.

**Acceptance Scenarios**:

1. **Given** a successful cataloged pull, **When** the cache path is inspected, **Then** it lives under the configured cache directory's `models/<domain>/` tree and the filename does not contain the upstream repository string, upstream filename, or download URL.
2. **Given** two processes pulling the same uncached alias at the same time, **When** both complete, **Then** they serialize on one lock per artifact: the second waits, then reuses a successful result or fails with the same class of download error if the first attempt did not produce a valid file; the final file is not truncated or mixed from both writers.
3. **Given** one or more cached aliases, **When** the developer runs `ceia-aisdk model list`, **Then** the command shows each cached alias and its size.
4. **Given** a cached alias, **When** the developer runs `ceia-aisdk model rm <alias>`, **Then** the cached file and its lock are removed, and a subsequent `list` no longer includes that alias.
5. **Given** `model info` or a public exception string for a cataloged alias, **When** the output is inspected, **Then** it does not print the upstream repository, upstream filename, or download URL.

---

### User Story 4 - View Public Metadata Without License Blocking (Priority: P2)

As a commercial developer, I want to see the license family and commercial-use flag so that I can make my own compliance decision, without the SDK refusing to pull or load the model.

**Why this priority**: License transparency is required for commercial adoption, but blocking on license would contradict the ratified product decision and delay first-chat.

**Independent Test**: Call `ceia-aisdk model info` and `get_public_metadata` for a cataloged alias and confirm the returned fields and the absence of a license-based refusal.

**Acceptance Scenarios**:

1. **Given** a cataloged alias, **When** the developer runs `ceia-aisdk model info <alias>` or calls `get_public_metadata(alias)`, **Then** only the public fields are returned: `license_family`, `commercial_use`, `context_length`, `size_gb`, `capabilities`, and `quantization_class`.
2. **Given** any license family in the catalog, **When** the developer pulls or ensures the alias locally, **Then** the SDK does not refuse the operation because of the license, and no `LicenseError` exists in this feature.
3. **Given** `ceia-aisdk model info --help`, **When** a developer reads it, **Then** it states that catalog authenticity is not verified in this increment and that integrity is the artifact checksum.

---

### User Story 5 - Use a Private or Air-Gapped Catalog (Priority: P2)

As an operator, I want to point the SDK at my own catalog so that downloads do not depend on the public organization, including in air-gapped networks.

**Why this priority**: Enterprises cannot adopt a registry that can only fetch from the public host, and continuous integration still needs local fixtures rather than multi-gigabyte production weights.

**Independent Test**: Point `CEIA_AISDK_CATALOG` at a valid local catalog and at an invalid one; pull using the override; confirm the bundled catalog remains the default when the variable is unset.

**Acceptance Scenarios**:

1. **Given** `CEIA_AISDK_CATALOG` set to a local path or HTTP URL for a catalog that uses the documented schema, **When** an alias is resolved or pulled, **Then** the SDK uses that catalog's locations and does not fall back to the public organization.
2. **Given** that `CEIA_AISDK_CATALOG` is unset, **When** the registry is used, **Then** the catalog bundled with the installed SDK is the source of truth for that version.
3. **Given** a catalog that does not match the documented schema, **When** it is loaded, **Then** the SDK raises `AISDKError` or `DownloadError` with remediation that points the operator at the schema.
4. **Given** a remote or local catalog override in this feature, **When** it is loaded, **Then** the SDK does not require a digital signature; the authenticity risk is documented for the operator.

---

### User Story 6 - Warm Essential Aliases (Priority: P2)

As a developer preparing a demo or an offline machine, I want a single command to download the essential aliases that the installed catalog actually contains so that I can populate the cache without assembling a custom list.

**Why this priority**: The program moved `--essentials` into this feature so the cache can be warmed without a desktop bundle or a public release; it is valuable only after a single-alias pull already works.

**Independent Test**: Run `ceia-aisdk model pull --essentials` against a catalog that contains `llm/small` and against a catalog that omits an essential name, and inspect only the model cache.

**Acceptance Scenarios**:

1. **Given** a catalog that includes `llm/small` at minimum, **When** the developer runs `ceia-aisdk model pull --essentials`, **Then** each essential alias that is present is downloaded into the model cache under the configured cache directory.
2. **Given** an essential name that is missing from the active catalog, **When** `--essentials` runs, **Then** the command warns and continues; it does not crash.
3. **Given** a successful essentials pull, **When** the cache is inspected, **Then** only `~/.ceia-aisdk/models/` (or the configured cache equivalent) is warmed; no distribution artifact is created.

---

### User Story 7 - Bypass the Catalog with a Custom Source (Priority: P3)

As a developer who needs a specific upstream file or a local weight, I want documented `hf://` and filesystem-path bypasses so that opacity does not block debugging or bring-your-own-model workflows.

**Why this priority**: Bypasses are the sanctioned escape hatch for opacity; they must exist but must not become the default path for first-chat.

**Independent Test**: Pull or ensure a local file and an `hf://` reference; confirm custom storage metadata and that cataloged `info` opacity is unchanged.

**Acceptance Scenarios**:

1. **Given** a local filesystem path to a model file, **When** the developer requests it through the documented bypass, **Then** the SDK stores it as a custom cache entry with source metadata `bypass` and does not rewrite it to a catalog opaque name.
2. **Given** an `hf://` reference, **When** the developer requests it through the documented bypass, **Then** the SDK stores it as a custom cache entry with source metadata `bypass` and does not rewrite the filename into the opaque catalog layout.
3. **Given** a bypassed custom entry, **When** `model info` is used on a cataloged alias, **Then** cataloged aliases remain opaque; the bypass does not cause cataloged `info` output to reveal upstream repository names.

---

### Edge Cases

- An alias contains path separators, `..`, or other characters that could be used to write outside the model cache.
- `CEIA_AISDK_CATALOG` points at a local path outside the expected catalog file, a directory, an empty file, or a file the process cannot read.
- A private catalog lists a location that would cause the downloader to write outside the cache directory or its temporary directory.
- The cache directory does not exist yet, is not writable, or lives on a filesystem that does not support locks.
- A lock is left behind after a crash; a later pull must still complete or fail with remediation rather than hang indefinitely.
- A warm-cache pull runs while another process is still writing the same artifact.
- Offline mode is enabled but the alias is already cached; the local file must be reused without a network attempt.
- A single URL fails (network error, server error, timeout); there is no second host to try.
- Progress indication runs in a non-interactive terminal or with output redirected to a file; the command must still complete and remain readable.
- `@latest` and an explicit `@N` that currently equals latest are requested in the same installed version; both must identify the same artifact.
- `model rm` is invoked for an alias that is not cached; the command must fail in an actionable way without deleting unrelated files.
- `model verify` runs with an empty cache; it succeeds without claiming that missing files are valid.
- A bypass path does not exist, or an `hf://` bypass fails; the error must not be confused with a catalog miss.
- Logs at `WARNING` or `ERROR` must not include the internal download URL unless debug logging is explicitly enabled.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The product MUST provide the `ceia-aisdk model` command group, and root help MUST list `model`.
- **FR-002**: The `model` group MUST provide `pull`, `list`, `rm`, `info`, `verify`, and `where`, each with complete help text and at least one executable example.
- **FR-003**: `ceia-aisdk model pull <alias>` MUST download the resolved cataloged artifact when it is not already valid in the cache.
- **FR-004**: `ceia-aisdk model pull --essentials` MUST download the essential aliases that exist in the active catalog, including `llm/small` when present, warn when an essential name is absent, and MUST NOT treat a missing essential name as a crash.
- **FR-005**: `ceia-aisdk model list` MUST show cached aliases and their sizes.
- **FR-006**: `ceia-aisdk model rm <alias>` MUST delete the cached file and its lock for that alias.
- **FR-007**: `ceia-aisdk model info <alias>` MUST print only the public metadata block.
- **FR-008**: `ceia-aisdk model verify` MUST rehash cached cataloged artifacts against the catalog and exit with a nonzero code on mismatch.
- **FR-009**: `ceia-aisdk model where <alias>` MUST print the absolute cache path of a cached alias.
- **FR-010**: The SDK MUST resolve these alias forms for cataloged models: `llm/small`, `llm/small@N`, and `llm/small@latest`.
- **FR-011**: The `model` CLI MUST treat an unqualified name such as `small` as `llm/<name>`.
- **FR-012**: The public programmatic registry surface MUST require a domain-qualified alias or an explicit domain context.
- **FR-013**: `@latest` MUST be pinned by the installed SDK version and MUST NOT trigger a silent remote catalog refresh.
- **FR-014**: An unknown catalog alias MUST raise `ModelNotFoundError` with nonempty remediation and the aliases available in the same domain.
- **FR-015**: The SDK MUST provide `resolve(alias)` to map a public alias to a catalog identity without downloading.
- **FR-016**: The SDK MUST provide `ensure_local(alias)` that returns the local cache path of a valid copy, downloading and verifying when needed.
- **FR-017**: The SDK MUST provide `get_public_metadata(alias)` that returns only `license_family`, `commercial_use`, `context_length`, `size_gb`, `capabilities`, and `quantization_class`.
- **FR-018**: Downstream modules MUST be able to obtain a local path through `ensure_local` without depending on CLI parsing.
- **FR-019**: Every cataloged artifact MUST declare exactly one download location and a mandatory checksum; a failing location MUST surface as `DownloadError` with nonempty remediation.
- **FR-020**: This feature MUST NOT implement host failover, official mirrors, or a second download location for the same artifact.
- **FR-021**: Cataloged downloads MUST be resumable after interruption, including after a hard process kill once at least 8 MB have been received.
- **FR-022**: A cataloged file MUST be visible at its final cache path only after its checksum matches the catalog; a mismatch MUST discard the candidate and MUST NOT promote it.
- **FR-023**: The checksum algorithm for cataloged artifacts MUST be SHA-256.
- **FR-024**: A warm-cache `pull` or `ensure_local` for a valid cached alias MUST complete in 2 seconds or less on reference local storage and MUST NOT start a network download.
- **FR-025**: When `AISDKConfig.offline` is true (including `CEIA_AISDK_OFFLINE=1`) and the alias is not valid in the cache, pull and `ensure_local` MUST fail within 100 ms with `DownloadError` and MUST NOT attempt to open a network connection.
- **FR-026**: Cached cataloged files MUST be stored under `<cache_dir>/models/<domain>/` with an opaque filename that does not contain the upstream repository, upstream filename, or URL.
- **FR-027**: The default cache directory remains the expanded `~/.ceia-aisdk` from the foundation configuration; model files MUST use that configuration's `cache_dir`.
- **FR-028**: Each artifact MUST have one lock; concurrent processes MUST wait for the holder and then reuse a valid result or fail without corrupting the file.
- **FR-029**: `model info`, `get_public_metadata`, and public exception strings for cataloged aliases MUST NOT reveal the upstream repository, upstream filename, or download URL.
- **FR-030**: Logs at `WARNING` or `ERROR` MUST NOT include the internal download URL unless debug logging is explicitly enabled.
- **FR-031**: The SDK MUST NOT raise or define `LicenseError`; license fields are informational and MUST NOT block pull or `ensure_local`.
- **FR-032**: The SDK MUST NOT implement catalog signatures, `CatalogSignatureError`, or an unsigned-catalog escape flag in this feature.
- **FR-033**: `CEIA_AISDK_CATALOG` MUST accept a local path or an HTTP URL to a catalog that uses the same schema as the bundled catalog.
- **FR-034**: An invalid catalog schema MUST raise `AISDKError` or `DownloadError` with remediation that references the schema.
- **FR-035**: When `CEIA_AISDK_CATALOG` is unset, the catalog bundled with the installed package MUST be used, and it MUST NOT be treated as a public API surface.
- **FR-036**: Documented bypasses `hf://...` and a local filesystem path MUST be stored as custom entries with metadata `source=bypass` and MUST NOT be rewritten to an opaque catalog filename.
- **FR-037**: Alias values and catalog-defined destinations MUST be sanitized so that the downloader cannot write outside `cache_dir` or the cache temporary directory.
- **FR-038**: All public failures in this feature MUST derive from `AISDKError` and expose `.remediation` as a nonempty string; download failures MUST use `DownloadError` and missing aliases MUST use `ModelNotFoundError`.
- **FR-039**: User-facing pull operations MUST show progress when a download occurs.
- **FR-040**: This feature MUST NOT publish the package to the public index; installation remains from the repository.
- **FR-041**: Distribution artifacts MUST NOT embed model weights; weights live only in the runtime cache.
- **FR-042**: Help for `model info` and troubleshooting documentation MUST state that remote catalog authenticity is not verified in this increment and that integrity is the artifact checksum.
- **FR-043**: The documentation increment for this feature MUST describe alias forms, CLI commands, `ensure_local`, opacity, bypasses, `CEIA_AISDK_CATALOG`, offline behavior, and the unsigned-catalog risk.

### Scope Boundaries

Included in this feature:

- Versioned opaque aliases and the bundled catalog for the installed SDK version.
- Integrity-checked, resumable download of cataloged artifacts.
- Deterministic model cache under the foundation cache directory.
- The `ceia-aisdk model` command group and the `resolve` / `ensure_local` / `get_public_metadata` contract for later modules.
- Private catalog override, offline refusal of downloads, and documented catalog bypasses.
- `model pull --essentials` as a cache-warming shortcut for aliases that exist in the catalog.

Explicitly excluded:

- Catalog signatures, Ed25519, `catalog.yaml.sig`, `CatalogSignatureError`, and `CEIA_AISDK_ALLOW_UNSIGNED_CATALOG`.
- Official mirrors and multi-host failover.
- LLM, voice, vision, or RAG inference, and any device selection based on `size_gb` versus available memory.
- Torrent, a proprietary content network, desktop packaging, and `bundle create`.
- Publishing the public model organization or uploading `ceia-aisdk` to the public index.
- `LicenseError` and license-based blocking of pull or load.
- Windows, Apple Silicon, ROCm, and Vulkan.

### Key Entities

- **Model Alias**: A public, versionable name in the form `domain/size` with optional `@N` or `@latest`, used by people and later modules instead of an upstream filename.
- **Catalog Entry**: The installed mapping from an alias to one download location, a mandatory checksum, size data, and a public metadata block.
- **Public Metadata**: The disclosable subset of an entry: license family, commercial-use flag, context length, approximate size, capabilities, and quantization class.
- **Cached Artifact**: A local, integrity-checked file stored at an opaque path under the model cache, together with its lock and any bypass metadata.
- **Catalog Override**: An operator-supplied catalog location (`CEIA_AISDK_CATALOG`) that replaces the bundled catalog for resolution and download.
- **Bypass Source**: A developer-supplied `hf://` reference or local path stored as a custom cache entry without catalog opacity rewriting.
- **Registry Error**: A public failure (`ModelNotFoundError` or `DownloadError`) with mandatory remediation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a reference Linux x86_64 machine with a warm cache, 100% of repeated pulls of a cached alias complete in 2 seconds or less and start zero network downloads.
- **SC-002**: After a hard interruption once at least 8 MB have been received, 100% of retries of the same cataloged alias finish from the already transferred bytes, and the completed file matches the catalog checksum.
- **SC-003**: 100% of checksum mismatches prevent a file from appearing at the final cache path and surface an actionable download failure.
- **SC-004**: 100% of `model info` outputs and public exception strings for cataloged aliases contain no upstream repository name, upstream filename, or download URL.
- **SC-005**: When offline mode is enabled and the alias is not cached, 100% of pull and `ensure_local` attempts fail within 100 ms with an actionable download error and zero connection attempts.
- **SC-006**: 100% of automated alias-resolution cases for `@N`, `@latest`, unqualified CLI `small`, domain-qualified names, and unknown names produce the specified identity or `ModelNotFoundError`.
- **SC-007**: In a concurrent-pull test of the same uncached alias, 100% of runs leave a single valid file or a clean failure, with no truncated or mixed content.
- **SC-008**: 100% of `CEIA_AISDK_CATALOG` schema-violation cases fail with remediation that points at the schema, and 100% of valid override cases fetch only from that catalog.
- **SC-009**: 100% of `--essentials` runs against a catalog that contains `llm/small` place that alias in the model cache; missing essential names produce a warning rather than a crash.
- **SC-010**: In an evaluation with at least five representative developers, at least 90% can pull `llm/small`, inspect public metadata, and locate the cached file on the first attempt without reading source code.

## Assumptions

- PRD-00 is available: installable package, `AISDKConfig` (`cache_dir`, `offline`, log level), `AISDKError` with `.remediation`, and the `ceia-aisdk` command.
- Linux x86_64 remains the only supported platform; Ubuntu 22.04 or later is the reference environment.
- On 2026-09-01 the Hugging Face organization `ceia-aisdk` published opaque version-1 artifacts for `llm/small`, `llm/medium`, and `llm/large`. The bundled catalog MUST pin those three aliases to those published files. Checksums, sizes, and download locations are recorded in [contracts/catalog.md](contracts/catalog.md).
- Automated tests MUST NOT download those production weights. Integration evidence uses a fixture of at least 16 MB with a known catalog checksum, injected through `CEIA_AISDK_CATALOG` or an equivalent test catalog, so resume and tamper cases stay local.
- The essential set in this increment is whatever the active catalog marks as essential, with `llm/small` as the only mandatory essential name. `llm/medium` and `llm/large` are cataloged and pullable but are not required by `--essentials`. Voice and embedding aliases may be absent and must only warn.
- Unqualified CLI names default to the `llm` domain because this increment's primary artifact is the small language-model alias.
- `get_public_metadata` is the public programmatic name for the public metadata contract; later planning may expose it through a registry object as long as the name and fields remain stable.
- Bypasses do not use a catalog checksum; the developer who supplies `hf://` or a local path accepts responsibility for that file.
- An unsigned catalog override is an accepted risk until a future signing feature; the default remains the bundled catalog.
- A single failing download location is a hard failure; operators who need another host supply a private catalog.
- `size_gb` is recorded here for later device-selection rules and is not used to choose CPU or GPU in this feature.
- This feature does not upload to the public index; the wheel that will later be published in PRD-02 will already include this registry.
- The decisions ratified in the PRD program on 2026-09-01 and PRD-01 are the normative sources for this specification.
- The ratified project constitution, version 1.0.0, governs this feature and all downstream SpecKit artifacts.

### Dependencies

- This feature depends on the public contracts of `001-sdk-foundations`: package identity, `AISDKConfig`, `cache_dir`, `offline`, logging namespace, error hierarchy, and the `ceia-aisdk` command.
- Later LLM, voice, vision, and RAG features depend on `resolve`, `ensure_local`, `get_public_metadata`, and `size_gb`.
- Production pulls of curated aliases use the published `ceia-aisdk` artifacts. Automated tests MUST still serve cataloged fixtures locally and MUST NOT require the public hosting organization at runtime.
- Device selection that compares free memory with `size_gb` remains out of scope until the LLM feature.
