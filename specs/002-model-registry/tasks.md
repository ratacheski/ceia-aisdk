---

description: "Implementation tasks for the CEIA AI SDK model registry and cache"
---

# Tasks: Model Registry and Cache

**Input**: Design documents from `specs/002-model-registry/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`,
`quickstart.md`, and constitution version 1.0.0

**Tests**: Mandatory. Every behavior task follows red-green-refactor: write and run the listed
test first, verify that it fails for the expected reason, then implement the minimum behavior.

**Organization**: Tasks are grouped by user story. P1 stories follow technical dependency
(resolve → download → cache). P2/P3 stories reuse that core and stay independently testable at
their checkpoints.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel after its explicit prerequisites because it changes different
  files.
- **[Story]**: Maps the task to a user story from `spec.md`.
- Every task names the exact file or files it changes or validates.

## Phase 1: Setup

**Purpose**: Add runtime dependencies, registry package layout, and shared test fixtures.

- [ ] T001 Add `httpx` and `pyyaml` as runtime dependencies with `uv add` and commit the lock
      in `pyproject.toml` and `uv.lock`
- [ ] T002 [P] Create the registry package skeleton with English module docstrings in
      `src/ceia_aisdk/registry/__init__.py`, `src/ceia_aisdk/registry/catalog.py`,
      `src/ceia_aisdk/registry/downloader.py`, and `src/ceia_aisdk/registry/cache.py`
- [ ] T003 [P] Add a generated ≥ 16 MiB fixture, a loopback HTTP server with `Range` and
      request counting, isolated `cache_dir`, and `pytest.mark.enable_socket` helpers in
      `tests/conftest.py`

**Checkpoint**: `uv lock --check` and `uv sync --locked --all-groups --all-extras` succeed.
`import ceia_aisdk` still does not load `httpx` or `yaml`.

---

## Phase 2: Foundational Shared Contracts

**Purpose**: Error types, catalog schema, path sanitization, and the bundled production catalog
that every story uses.

**Critical**: No user-story implementation begins until these tests have failed and the shared
contracts pass.

### Tests First

- [ ] T004 [P] Write and run failing `ModelNotFoundError` and `DownloadError` hierarchy,
      nonempty remediation, opacity of origin URLs, and English docstring tests in
      `tests/contract/test_public_errors.py`
- [ ] T005 [P] Write and run failing schema, `latest` pin, single-URL, SHA-256, essentials,
      and invalid-document tests in `tests/unit/test_registry_catalog.py`
- [ ] T006 [P] Write and run failing alias/`..`/absolute-path/cache-destination sanitization
      tests in `tests/unit/test_registry_sanitize.py`

### Minimal Implementation

- [ ] T007 [P] Implement documented `ModelNotFoundError` and `DownloadError` in
      `src/ceia_aisdk/errors.py` and re-export them from `src/ceia_aisdk/__init__.py` without
      importing `ceia_aisdk.registry`
- [ ] T008 Implement catalog document loading, schema validation, and production pin records
      in `src/ceia_aisdk/registry/catalog.py`
- [ ] T009 [P] Write the bundled production catalog for `llm/small@1`, `llm/medium@1`, and
      `llm/large@1` from `specs/002-model-registry/contracts/catalog.md` in
      `src/ceia_aisdk/registry/_internal_catalog.yaml` and include it as package data in
      `pyproject.toml`
- [ ] T010 Implement destination sanitization so writes cannot escape `cache_dir/models` or
      `cache_dir/models/.tmp` in `src/ceia_aisdk/registry/cache.py`

**Checkpoint**: `uv run pytest tests/contract/test_public_errors.py
tests/unit/test_registry_catalog.py tests/unit/test_registry_sanitize.py` passes.
`import ceia_aisdk` still does not import `yaml` or `httpx`.

---

## Phase 3: User Story 1 — Resolve a Versioned Alias (Priority: P1) MVP

**Goal**: Map `llm/small`, `@N`, `@latest`, CLI unqualified `small`, and unknown names to a
stable identity without downloading.

**Independent Test**: Call `resolve` for known aliases and an unknown alias with no network;
confirm CLI context treats `small` as `llm/small` and programmatic `small` is rejected.

### Tests First

- [ ] T011 [P] [US1] Write and run failing `@N`, `@latest`, domain-qualified, unqualified
      programmatic rejection, CLI `small` → `llm/small`, and `ModelNotFoundError` suggestion
      tests in `tests/unit/test_registry_resolve.py`
- [ ] T012 [P] [US1] Write and run failing `resolve` signature, `ResolvedAlias` opacity, and
      no-download contract tests in `tests/contract/test_registry_api.py`
- [ ] T013 [P] [US1] Write and run failing root-help `model` discovery and `ceia-aisdk model
      --help` command-list tests in `tests/contract/test_model_cli_help.py`
- [ ] T014 [P] [US1] Extend and run failing fresh-import tests that `httpx` and `yaml` stay
      unloaded in `tests/contract/test_package_api.py`

### Minimal Implementation

- [ ] T015 [US1] Implement `resolve`, `ResolvedAlias`, and CLI-versus-programmatic alias rules
      in `src/ceia_aisdk/registry/catalog.py` and export them from
      `src/ceia_aisdk/registry/__init__.py`
- [ ] T016 [US1] Mount the Typer `model` sub-application with complete English group help in
      `src/ceia_aisdk/_model_cli.py` and `src/ceia_aisdk/cli.py`
- [ ] T017 [US1] Run and make the US1 suite pass through `uv` for
      `tests/unit/test_registry_resolve.py`, `tests/contract/test_registry_api.py`,
      `tests/contract/test_model_cli_help.py`, and `tests/contract/test_package_api.py`

**Checkpoint**: Aliases resolve from the bundled catalog with zero HTTP. Root help lists
`model`. Package import remains lightweight.

---

## Phase 4: User Story 2 — Download with Integrity (Priority: P1)

**Goal**: `ensure_local` and `model pull` download one URL, resume, verify SHA-256, refuse
offline misses quickly, and expose `where` / `verify`.

**Independent Test**: Against the loopback fixture only, pull, interrupt after ≥ 8 MiB and
resume, tamper one byte, run `verify` and `where`, warm-cache pull ≤ 2 s with zero GET, and
offline miss ≤ 100 ms.

### Tests First

- [ ] T018 [P] [US2] Write and run failing pull, checksum promotion, and `where` tests in
      `tests/integration/test_model_download.py`
- [ ] T019 [P] [US2] Write and run failing resume-after-interrupt tests that count `Range`
      requests in `tests/integration/test_model_resume.py`
- [ ] T020 [P] [US2] Write and run failing offline cache-miss timing and no-socket tests in
      `tests/integration/test_model_offline.py`
- [ ] T021 [P] [US2] Write and run failing warm-cache ≤ 2 s and zero-GET tests in
      `tests/performance/test_warm_cache.py`
- [ ] T022 [P] [US2] Write and run failing offline-miss ≤ 100 ms tests in
      `tests/performance/test_offline_miss.py`
- [ ] T023 [P] [US2] Extend `tests/contract/test_model_cli_help.py` with failing `pull`,
      `where`, and `verify` help, examples, and unsigned-catalog note on `info --help` (do not
      execute production `pull llm/small` examples)

### Minimal Implementation

- [ ] T024 [US2] Implement resumable HTTP download, SHA-256, tmp/`fsync`/replace, and lazy
      `httpx` import in `src/ceia_aisdk/registry/downloader.py`
- [ ] T025 [US2] Implement `ensure_local`, sidecar write, offline short-circuit, and corrupt
      re-download in `src/ceia_aisdk/registry/cache.py` and
      `src/ceia_aisdk/registry/__init__.py`
- [ ] T026 [US2] Implement `model pull ALIAS`, `model where`, and `model verify` with TTY
      progress and English failure/`remediation` output in `src/ceia_aisdk/_model_cli.py`
- [ ] T027 [US2] Honor `AISDKConfig.offline` / `CEIA_AISDK_OFFLINE` before opening a client in
      `src/ceia_aisdk/registry/cache.py` and `src/ceia_aisdk/registry/downloader.py`
- [ ] T028 [US2] Run and make the US2 download, resume, offline, performance, and help suites
      pass through `uv` using only loopback fixtures

**Checkpoint**: Fixture pulls are integrity-checked, resumable, and offline-safe. Production
Hugging Face weights are not downloaded by CI.

---

## Phase 5: User Story 3 — Keep the Cache Opaque and Concurrent (Priority: P1)

**Goal**: Opaque cache names, per-artifact locks, `list`/`rm`, and no origin leakage in paths
or public exception strings.

**Independent Test**: Inspect cache paths after a fixture pull; run two concurrent pulls of the
same alias; `list` then `rm`; confirm `info`/exception snapshots contain no upstream identity.

### Tests First

- [ ] T029 [P] [US3] Write and run failing opaque-path and sidecar layout tests in
      `tests/unit/test_registry_cache.py`
- [ ] T030 [P] [US3] Write and run failing two-process concurrent-pull tests in
      `tests/integration/test_model_concurrency.py`
- [ ] T031 [P] [US3] Write and run failing `list`/`rm` CLI tests in
      `tests/integration/test_model_cli.py`
- [ ] T032 [P] [US3] Write and run failing `info` and `str(exception)` opacity snapshots in
      `tests/contract/test_registry_opacity.py`

### Minimal Implementation

- [ ] T033 [US3] Store cataloged files as `<cache_dir>/models/<domain>/<size>-v<N>.bin` with
      sidecar and lock paths in `src/ceia_aisdk/registry/cache.py`
- [ ] T034 [US3] Implement exclusive `fcntl.flock` wait-and-reuse in
      `src/ceia_aisdk/registry/cache.py`
- [ ] T035 [US3] Implement `model list` and `model rm` in `src/ceia_aisdk/_model_cli.py`
- [ ] T036 [US3] Keep WARNING/ERROR logs and public exceptions free of catalog URLs in
      `src/ceia_aisdk/registry/downloader.py`, `src/ceia_aisdk/registry/catalog.py`, and
      `src/ceia_aisdk/errors.py`
- [ ] T037 [US3] Run and make the US3 cache, concurrency, CLI, and opacity suites pass through
      `uv`

**Checkpoint**: Two processes cannot mix a file. Cache names and public output stay opaque.

---

## Phase 6: User Story 4 — View Public Metadata Without License Blocking (Priority: P2)

**Goal**: `get_public_metadata` and `model info` return only the public block. Licenses never
block pull. Help states checksum integrity, not catalog authenticity.

**Independent Test**: Call `get_public_metadata` and `model info` on a cataloged alias; pull a
fixture whose public license would be commercially sensitive; confirm no `LicenseError`.

### Tests First

- [ ] T038 [P] [US4] Extend and run failing public-field-only `get_public_metadata` tests in
      `tests/contract/test_registry_api.py`
- [ ] T039 [P] [US4] Write and run failing `model info` field and help-text tests in
      `tests/integration/test_model_cli.py`
- [ ] T040 [P] [US4] Write and run a failing assertion that `LicenseError` is absent and pull
      ignores `commercial_use` in `tests/contract/test_public_errors.py` and
      `tests/integration/test_model_download.py`

### Minimal Implementation

- [ ] T041 [US4] Implement `PublicModelMetadata` and `get_public_metadata` in
      `src/ceia_aisdk/registry/catalog.py` and `src/ceia_aisdk/registry/__init__.py`
- [ ] T042 [US4] Implement `model info` output and `--help` authenticity warning in
      `src/ceia_aisdk/_model_cli.py`
- [ ] T043 [US4] Run and make the US4 API, CLI, and license-non-blocking suites pass through
      `uv`

**Checkpoint**: Public metadata is complete and informational. Pull is never license-gated.

---

## Phase 7: User Story 5 — Use a Private or Air-Gapped Catalog (Priority: P2)

**Goal**: `CEIA_AISDK_CATALOG` replaces the bundled catalog with no merge, no signature, and
schema-failure remediation.

**Independent Test**: Point the variable at a valid local YAML and at an invalid one; pull from
the override; unset the variable and confirm the bundled catalog returns.

### Tests First

- [ ] T044 [P] [US5] Write and run failing local and HTTP override, no-fallback, and invalid
      schema tests in `tests/integration/test_catalog_override.py`
- [ ] T045 [P] [US5] Extend catalog unit tests for override selection in
      `tests/unit/test_registry_catalog.py`

### Minimal Implementation

- [ ] T046 [US5] Load `CEIA_AISDK_CATALOG` (path or HTTP) with unsigned acceptance and schema
      `DownloadError` remediation in `src/ceia_aisdk/registry/catalog.py`
- [ ] T047 [US5] Document the unsigned-catalog risk in `README.md` and
      `src/ceia_aisdk/_model_cli.py` help
- [ ] T048 [US5] Run and make the override suites pass through `uv`

**Checkpoint**: Operators can replace the public host. Invalid schema fails with remediation.
Tests still never hit production weights unless an override is explicit.

---

## Phase 8: User Story 6 — Warm Essential Aliases (Priority: P2)

**Goal**: `model pull --essentials` downloads aliases listed in the active catalog (`llm/small`
required in the bundled file) and warns instead of crashing when a name is missing.

**Independent Test**: Run `--essentials` against a catalog that contains `llm/small` and one
that omits an essential name; inspect only the model cache.

### Tests First

- [ ] T049 [P] [US6] Write and run failing present-alias download, missing-name warning, and
      no-distribution-artifact tests in `tests/integration/test_model_essentials.py`
- [ ] T050 [P] [US6] Extend `tests/contract/test_model_cli_help.py` with `--essentials` help
      and example text

### Minimal Implementation

- [ ] T051 [US6] Implement `model pull --essentials` in `src/ceia_aisdk/_model_cli.py` using
      the catalog `essentials` list
- [ ] T052 [US6] Run and make the essentials suite pass through `uv`

**Checkpoint**: `--essentials` warms `cache_dir/models` only. Missing essentials warn.

---

## Phase 9: User Story 7 — Bypass the Catalog with a Custom Source (Priority: P3)

**Goal**: `hf://` and local paths store custom `source=bypass` entries without opaque catalog
rewriting; cataloged `info` stays opaque.

**Independent Test**: `ensure_local` / `pull` a local file and an `hf://` fixture; confirm
sidecar `source=bypass` and unchanged cataloged `info`.

### Tests First

- [ ] T053 [P] [US7] Write and run failing local-path and `hf://` bypass tests in
      `tests/integration/test_model_bypass.py`

### Minimal Implementation

- [ ] T054 [US7] Implement path and `hf://` bypass storage under `models/custom/` with
      `source=bypass` in `src/ceia_aisdk/registry/cache.py` and
      `src/ceia_aisdk/registry/downloader.py`
- [ ] T055 [US7] Accept bypass tokens in `model pull` in `src/ceia_aisdk/_model_cli.py` and
      document them in `README.md`
- [ ] T056 [US7] Run and make the bypass suite pass through `uv` without leaking origin into
      cataloged `info`

**Checkpoint**: Bring-your-own-model works. Cataloged aliases remain opaque.

---

## Phase 10: Polish and Cross-Cutting Concerns

**Purpose**: Documentation, packaging, import budget, and full quickstart gates.

- [ ] T057 [P] Document aliases, CLI, `ensure_local`, opacity, bypasses, `CEIA_AISDK_CATALOG`,
      offline mode, and unsigned-catalog risk in English in `README.md`
- [ ] T058 [P] Complete Google-style English docstrings for every new public and non-public
      method in `src/ceia_aisdk/registry/`, `src/ceia_aisdk/_model_cli.py`,
      `src/ceia_aisdk/errors.py`, and `src/ceia_aisdk/cli.py`
- [ ] T059 Confirm the wheel/sdist contain `_internal_catalog.yaml`, exclude weight files, and
      still forbid `httpx`/`yaml` on `import ceia_aisdk` in
      `tests/integration/test_installed_artifacts.py` and
      `tests/contract/test_package_api.py`
- [ ] T060 Execute every validation scenario in `specs/002-model-registry/quickstart.md` with
      `uv`, using loopback fixtures only, and correct inaccurate expectations in that file
- [ ] T061 Run all locked quality, English-language, test, network-isolation, Python-matrix,
      wheel/sdist, and artifact gates without `uv publish`, resolving failures in
      `pyproject.toml`, `uv.lock`, `src/ceia_aisdk/`, `tests/`, `README.md`, and
      `specs/002-model-registry/quickstart.md`

**Checkpoint**: Constitutional gates pass. The registry is locally installable. No public PyPI
upload. CI never downloads production GGUF files.

---

## Dependencies and Execution Order

### Phase Dependencies

- Phase 1 has no prerequisites.
- Phase 2 depends on Phase 1 and blocks all user-story implementation.
- Phase 3 (US1) depends on Phase 2.
- Phase 4 (US2) depends on US1 because download uses `resolve`.
- Phase 5 (US3) depends on US2 because locks, list, and rm operate on cached files.
- Phase 6 (US4) depends on US1 for metadata and US2 for license-non-blocking pull.
- Phase 7 (US5) depends on US1 and US2 so overrides affect both resolve and pull.
- Phase 8 (US6) depends on US2 `pull`.
- Phase 9 (US7) depends on US2 `ensure_local` and US4 cataloged `info`.
- Phase 10 depends on every selected user story.

### User Story Completion Order

- **US1 (P1)**: Shared foundation → US1. MVP: resolve-only.
- **US2 (P1)**: US1 → US2. First useful product slice (pull a fixture).
- **US3 (P1)**: US2 → US3.
- **US4 (P2)**: US1 + US2 → US4.
- **US5 (P2)**: US1 + US2 → US5.
- **US6 (P2)**: US2 → US6.
- **US7 (P3)**: US2 + US4 → US7.

Each story remains independently testable at its checkpoint.

### TDD Ordering Within Every Story

1. Complete and run all “Tests First” tasks.
2. Confirm each new test fails for the expected missing behavior, not due to setup errors.
3. Implement the minimum behavior in task order.
4. Refactor only while the relevant suite remains green.
5. Run the story checkpoint before starting dependent implementation.

## Parallel Opportunities

### Setup and Shared Foundation

- After T001, T002 and T003 can run in parallel.
- T004, T005, and T006 can run in parallel.
- After matching tests fail, T007 and T009 can run in parallel with T008/T010 sequencing on
  `catalog.py` / `cache.py`.

### User Story 1

- T011, T012, T013, and T014 can be authored in parallel.

### User Story 2

- T018–T023 can be authored in parallel before implementation.

### User Story 3

- T029–T032 can run in parallel.

### User Story 4

- T038–T040 can run in parallel.

### User Story 5

- T044 and T045 can run in parallel.

### Polish

- T057, T058, and T059 can run in parallel after story checkpoints.

## Parallel Execution Examples

### User Story 1 tests

```bash
uv run pytest tests/unit/test_registry_resolve.py tests/contract/test_registry_api.py tests/contract/test_model_cli_help.py tests/contract/test_package_api.py
```

### User Story 2 tests

```bash
uv run pytest tests/integration/test_model_download.py tests/integration/test_model_resume.py tests/integration/test_model_offline.py tests/performance/test_warm_cache.py tests/performance/test_offline_miss.py
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `resolve("llm/small")` works from the bundled catalog with no network
5. Continue to US2 before any demo that must place a file in the cache

### Incremental Delivery

1. Setup + Foundational
2. US1 resolve → demo aliases
3. US2 pull fixture → demo integrity
4. US3 cache safety
5. US4 metadata
6. US5 private catalog
7. US6 essentials
8. US7 bypass
9. Polish and quality gates

### Parallel Team Strategy

After Phase 2:

- Developer A: US1 then US2 (critical path)
- Developer B: US4 API types after US1 `ResolvedAlias` exists (merge after US1)
- Developer C: test fixtures and opacity snapshots (files under `tests/`)

Do not parallelize US2 and US3 on `cache.py` in the same working tree.

## Notes

- [P] tasks change different files and have no unmet dependencies.
- Never execute `ceia-aisdk model pull llm/small` in CI against the bundled production catalog.
- Verify tests fail before implementing.
- Commit after each task or logical group.
- Stop at any checkpoint to validate the story independently.
- No `uv publish` in this feature.
