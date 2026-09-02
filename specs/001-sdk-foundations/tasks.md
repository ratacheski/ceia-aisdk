---

description: "Implementation tasks for CEIA AI SDK operational foundations"
---

# Tasks: CEIA AI SDK Operational Foundations

**Input**: Design documents from `specs/001-sdk-foundations/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`,
`quickstart.md`, and constitution version 1.0.0

**Tests**: Mandatory. Every behavior task follows red-green-refactor: write and run the listed
test first, verify that it fails for the expected reason, then implement the minimum behavior.

**Organization**: Tasks are grouped by user story. P1 stories are ordered by technical
dependency; P2 stories follow after the diagnostic foundation they reuse.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel after its explicit prerequisites are complete because it changes
  different files.
- **[Story]**: Maps the task to a user story from `spec.md`.
- Every task names the exact file or files it changes or validates.

## Phase 1: Setup

**Purpose**: Establish the `uv`-managed package, development tools, and shared test environment.

- [X] T001 Initialize the `uv_build` project, Python 3.11-3.13 metadata, `ceia-aisdk` console script, Typer/Rich runtime dependencies, empty `cuda` extra, development tool group, and tool configuration in `pyproject.toml` and `uv.lock`
- [X] T002 [P] Add Python, `uv`, test, build, and diagnostic-output exclusions to `.gitignore`
- [X] T003 [P] Create shared isolated-home, environment-cleanup, socket-blocking, and backend-import assertion fixtures in `tests/conftest.py`

**Checkpoint**: `uv lock --check` and `uv sync --locked --all-groups --all-extras` succeed.

---

## Phase 2: Foundational Shared Contracts

**Purpose**: Provide the error and logging primitives required by every user story.

**Critical**: No user-story implementation begins until these tests have failed and the shared
contracts pass.

### Tests First

- [X] T004 [P] Write and run failing public error hierarchy, nonempty remediation, and English docstring contract tests in `tests/contract/test_public_errors.py`
- [X] T005 [P] Write and run failing namespaced logger, `NullHandler`, root-logger isolation, and idempotent configuration tests in `tests/unit/test_logging.py`

### Minimal Implementation

- [X] T006 [P] Implement documented `AISDKError`, `ConfigError`, and `DeviceError` classes with validated message and remediation fields in `src/ceia_aisdk/errors.py`
- [X] T007 [P] Implement side-effect-safe namespace logging setup with English module and method docstrings in `src/ceia_aisdk/_logging.py`

**Checkpoint**: `uv run pytest tests/contract/test_public_errors.py tests/unit/test_logging.py`
passes without changing root logging configuration.

---

## Phase 3: User Story 1 — Install and Recognize the SDK Locally (Priority: P1) MVP

**Goal**: Build and install the local package, import `ceia_aisdk`, expose one consistent version,
and discover the fully documented `doctor` command through root help.

**Independent Test**: Build a local wheel, install it in an isolated `uv` environment, import
`ceia_aisdk`, compare its version with distribution metadata, and run `ceia-aisdk --help`.

### Tests First

- [X] T008 [P] [US1] Write and run failing package-name, version, lightweight-import, public-export, Python-range, and Linux-classifier contract tests in `tests/contract/test_package_api.py`
- [X] T009 [P] [US1] Write and run failing root and `doctor` help completeness, English text, command discovery, and executable-example tests in `tests/contract/test_cli_help.py`
- [X] T010 [P] [US1] Write and run failing wheel/sdist metadata, isolated installation, console-entry-point, artifact-content, size-budget, and no-publication tests in `tests/integration/test_installed_artifacts.py`
- [X] T011 [P] [US1] Write and run the failing fresh-process import p95 and forbidden-backend import tests in `tests/performance/test_import_timing.py`

### Minimal Implementation

- [X] T012 [US1] Implement the lightweight package root, metadata-backed `__version__`, public error exports, `NullHandler`, and English module docstring in `src/ceia_aisdk/__init__.py`
- [X] T013 [US1] Implement the Typer root application and documented `doctor` command shell with complete English help and examples in `src/ceia_aisdk/cli.py`
- [X] T014 [P] [US1] Replace the placeholder project README with English Linux x86_64 scope, `uv` contributor setup, local-install instructions, reserved CUDA-extra warning, CLI discovery examples, and PRD-02 publication boundary in `README.md`
- [X] T015 [US1] Complete package metadata and build inclusion rules until isolated wheel and sdist smoke tests pass in `pyproject.toml`, `uv.lock`, and `tests/integration/test_installed_artifacts.py`

**Checkpoint**: User Story 1 works from both local artifact types without loading inference
backends or publishing to PyPI.

---

## Phase 4: User Story 3 — Configure the SDK Predictably (Priority: P1)

**Goal**: Resolve immutable configuration independently per field using explicit arguments,
environment, TOML, and defaults.

**Independent Test**: Run the four-source precedence matrix for all fields under a temporary home
directory, including missing, empty, malformed, unreadable, and shadowed-invalid TOML cases.

### Tests First

- [X] T016 [P] [US3] Write and run failing field-by-field precedence, defaults, type validation, strict environment parsing, path expansion, missing/empty TOML, malformed TOML, and privacy tests in `tests/unit/test_config.py`
- [X] T017 [P] [US3] Extend and run failing immutability, slots, `AISDKConfig.load` signature, root export, and no-side-effect API contracts in `tests/contract/test_package_api.py`

### Minimal Implementation

- [X] T018 [US3] Implement immutable `AISDKConfig`, standard-library TOML loading, independent source resolution, strict validation, and privacy-safe `ConfigError` handling with English docstrings in `src/ceia_aisdk/config.py`
- [X] T019 [US3] Export `AISDKConfig` without importing CLI or hardware probes in `src/ceia_aisdk/__init__.py`
- [X] T020 [US3] Add English configuration precedence, TOML, environment, defaults, strict-value, and mixed-source examples to `README.md`
- [X] T021 [US3] Run and make the independent configuration and package API suites pass through `uv` for `tests/unit/test_config.py` and `tests/contract/test_package_api.py`

**Checkpoint**: User Story 3 passes independently with no directory creation, network call,
hardware probe, or root-logger mutation.

---

## Phase 5: User Story 2 — Diagnose Machine Readiness (Priority: P1)

**Goal**: Produce a complete, privacy-safe, copyable `doctor` report with CPU and mocked NVIDIA
coverage, deterministic output, and correct exit status.

**Independent Test**: Run `CEIA_AISDK_DEVICE=cpu uv run ceia-aisdk doctor`, verify exit code `0`,
all required fields, plain redirected output, the fixed copyable block, no private data, no
network, and completion within 5 seconds; repeat GPU paths with deterministic probe fixtures.

### Tests First

- [X] T022 [P] [US2] Write and run failing immutable diagnostic-check/report, usability, field-order, path-normalization, copy-block, and privacy tests in `tests/unit/test_diagnostics.py`
- [X] T023 [P] [US2] Write and run failing bounded NVIDIA process, CSV parsing, timeout, no-GPU, single-GPU, multi-GPU, prohibited-compute, MIG, and internal device-selection tests in `tests/unit/test_hardware.py`
- [X] T024 [P] [US2] Write and run failing installed `doctor` CPU/GPU/forced-CUDA, exit-code, stdout/stderr, redirected-output, `TERM=dumb`, `NO_COLOR`, terminal-width, and privacy tests in `tests/integration/test_doctor.py`
- [X] T025 [P] [US2] Write and run failing CPU-only 5-second timeout, 2-second probe timeout, zero-network, and no-inference-import tests in `tests/performance/test_doctor_timing.py`

### Minimal Implementation

- [X] T026 [US2] Implement private immutable probe records, one-shot `nvidia-smi` execution, strict bounded CSV parsing, sanitized probe status, and internal selection in `src/ceia_aisdk/hardware.py`
- [X] T027 [US2] Implement immutable diagnostic checks/reports, platform and package collection, privacy sanitization, deterministic field order, optional-group reporting, and copy-block serialization in `src/ceia_aisdk/_diagnostics.py`
- [X] T028 [US2] Complete `doctor` collection, Rich TTY rendering, deterministic plain rendering, help examples, and exit-code behavior in `src/ceia_aisdk/cli.py`
- [X] T029 [US2] Apply `AISDKConfig.log_level` only to the package namespace and connect diagnostic logging without root side effects in `src/ceia_aisdk/_logging.py` and `src/ceia_aisdk/cli.py`
- [X] T030 [US2] Run and make the independent diagnostic, hardware, CLI integration, timing, and network-isolation suites pass for `tests/unit/test_diagnostics.py`, `tests/unit/test_hardware.py`, `tests/integration/test_doctor.py`, and `tests/performance/test_doctor_timing.py`

**Checkpoint**: User Story 2 is complete on CPU and mocked NVIDIA environments; real NVIDIA
validation remains an explicit reference-machine gate.

---

## Phase 6: User Story 4 — Select CPU or CUDA Safely (Priority: P2)

**Goal**: Expose the direct Python hardware API with deterministic CPU/CUDA selection and
non-sensitive GPU information.

**Independent Test**: Call `detect_gpus()` and `get_device()` against absent, failed, single,
multiple, prohibited, MIG, and forced-index probe fixtures and verify return values, logging, and
`DeviceError` remediation.

### Tests First

- [X] T031 [P] [US4] Extend and run failing `GPUInfo`, `detect_gpus`, `get_device`, package-root export, signature, immutability, unit, and forbidden-import contracts in `tests/contract/test_package_api.py`
- [X] T032 [P] [US4] Extend and run failing direct-API CPU short-circuit, lowest-index selection, forced `cuda`, forced `cuda:N`, invalid syntax, quiet fallback, quoted-name, malformed-output, and VRAM invariant tests in `tests/unit/test_hardware.py`

### Minimal Implementation

- [X] T033 [US4] Implement documented public `GPUInfo`, `detect_gpus()`, and `get_device()` wrappers over the tested bounded snapshot and selection logic in `src/ceia_aisdk/hardware.py`
- [X] T034 [US4] Re-export the public hardware API while preserving the import-time and no-probe contracts in `src/ceia_aisdk/__init__.py`
- [X] T035 [US4] Add English CPU, automatic CUDA, forced CUDA, index semantics, MiB units, MIG limitation, and no-inference-guarantee examples to `README.md`
- [X] T036 [US4] Run and make the direct hardware API contract and unit suites pass for `tests/contract/test_package_api.py` and `tests/unit/test_hardware.py`

**Checkpoint**: User Story 4 is independently usable without `doctor`, model aliases, inference
dependencies, or network access.

---

## Phase 7: User Story 5 — Receive Actionable Failures (Priority: P2)

**Goal**: Ensure every public configuration and device failure is typed, privacy-safe, and
provides a concrete next action through both Python and CLI surfaces.

**Independent Test**: Trigger invalid configuration and unavailable forced CUDA through Python
and `doctor`, then verify the `AISDKError` hierarchy, nonempty English remediation, sanitized
output, and absence of native stack traces.

### Tests First

- [X] T037 [P] [US5] Extend and run failing empty-message rejection, empty-remediation rejection, exception chaining, `ConfigError`, `DeviceError`, and sanitized string contract tests in `tests/contract/test_public_errors.py`
- [X] T038 [P] [US5] Extend and run failing end-to-end invalid-TOML, invalid-environment, forced-CUDA, remediation-output, no-stack-trace, and no-file-content tests in `tests/integration/test_doctor.py`

### Minimal Implementation

- [X] T039 [P] [US5] Complete field/source-aware English `ConfigError` messages and concrete remediation without raw-value disclosure in `src/ceia_aisdk/config.py`
- [X] T040 [P] [US5] Complete unavailable-driver, no-GPU, invalid-index, invalid-syntax, and probe-failure `DeviceError` messages and remediation in `src/ceia_aisdk/hardware.py`
- [X] T041 [US5] Render public error remediation consistently in diagnostic checks, plain/Rich output, the copyable block, and stderr without native traces in `src/ceia_aisdk/_diagnostics.py` and `src/ceia_aisdk/cli.py`
- [X] T042 [US5] Add English troubleshooting examples for configuration and forced CUDA failures to `README.md`
- [X] T043 [US5] Run and make the error contract and end-to-end remediation suites pass for `tests/contract/test_public_errors.py` and `tests/integration/test_doctor.py`

**Checkpoint**: User Story 5 passes through Python and CLI, and automatic CPU fallback remains a
supported non-error state.

---

## Phase 8: Polish and Cross-Cutting Quality Gates

**Purpose**: Enforce the constitution and validate the complete local release candidate without
publishing it.

- [X] T044 [P] Add the Python 3.11-3.13 `uv` matrix, locked synchronization, lint, docstring, spelling, test, build, artifact inspection, and isolated smoke-test gates to `.github/workflows/ci.yml`
- [X] T045 [P] Audit and complete English module, class, function, and method docstrings against Ruff and pydoclint in `src/ceia_aisdk/__init__.py`, `src/ceia_aisdk/_diagnostics.py`, `src/ceia_aisdk/_logging.py`, `src/ceia_aisdk/cli.py`, `src/ceia_aisdk/config.py`, `src/ceia_aisdk/errors.py`, and `src/ceia_aisdk/hardware.py`
- [X] T046 Execute every validation scenario and command in `specs/001-sdk-foundations/quickstart.md`, correct any inaccurate expectation in that file, and remove temporary `doctor.txt` and `dist/` artifacts
- [X] T047 [P] Run the optional NVIDIA reference comparison and record the GPU name/index and ±256 MiB result, or the explicit absence of a suitable runner, in `specs/001-sdk-foundations/checklists/requirements.md`
- [X] T048 Run all locked quality, English-language, test, network-isolation, Python-matrix, wheel/sdist, metadata, artifact-content, and size gates without invoking `uv publish`, resolving failures in `pyproject.toml`, `uv.lock`, `src/ceia_aisdk/`, `tests/`, `README.md`, and `specs/001-sdk-foundations/quickstart.md`

**Checkpoint**: All constitutional gates pass, local artifacts are release-ready, and no public
upload has occurred.

---

## Dependencies and Execution Order

### Phase Dependencies

- Phase 1 has no prerequisites.
- Phase 2 depends on Phase 1 and blocks all user-story implementation.
- Phase 3 (US1) depends on Phase 2 and establishes the installable package and CLI surface.
- Phase 4 (US3) depends on US1 because it extends the installed package root.
- Phase 5 (US2) depends on US1 and US3 because `doctor` consumes package and configuration
  contracts.
- Phase 6 (US4) depends on US2's bounded probe and selection internals, then exposes them as the
  direct Python API.
- Phase 7 (US5) depends on US3, US2, and US4 so it can validate all concrete public failure paths.
- Phase 8 depends on every selected user story.

### User Story Completion Order

- **US1 (P1)**: Shared foundation → US1. No other story dependency.
- **US3 (P1)**: Shared foundation → US1 → US3.
- **US2 (P1)**: Shared foundation → US1 → US3 → US2.
- **US4 (P2)**: Shared foundation → US2 internals → US4 public API.
- **US5 (P2)**: Shared foundation → US3 + US2 + US4 → US5 hardening.

Each story remains independently testable at its checkpoint even where implementation reuses an
earlier technical prerequisite.

### TDD Ordering Within Every Story

1. Complete and run all “Tests First” tasks.
2. Confirm each new test fails for the expected missing behavior, not due to setup errors.
3. Implement the minimum behavior in task order.
4. Refactor only while the relevant suite remains green.
5. Run the story checkpoint before starting dependent implementation.

## Parallel Opportunities

### Setup and Shared Foundation

- After T001, T002 and T003 can run in parallel.
- T004 and T005 can run in parallel.
- After their matching tests fail, T006 and T007 can run in parallel.

### User Story 1

- T008, T009, T010, and T011 can be authored and executed in parallel.
- T014 can proceed in parallel with source implementation after required commands are known.

### User Story 3

- T016 and T017 can run in parallel.

### User Story 2

- T022, T023, T024, and T025 can run in parallel before implementation.

### User Story 4

- T031 and T032 can run in parallel.

### User Story 5

- T037 and T038 can run in parallel.
- After both tests fail, T039 and T040 can run in parallel.

### Polish

- T044, T045, and T047 can run in parallel after all story checkpoints.

## Parallel Execution Examples

### User Story 1

- Developer A: T008, package API contracts.
- Developer B: T009, CLI help contracts.
- Developer C: T010, artifact installation contracts.
- Developer D: T011, fresh-process import contracts.

### User Story 3

- Developer A: T016, source-precedence and validation tests.
- Developer B: T017, public configuration API contracts.

### User Story 2

- Developer A: T022, diagnostic data-model tests.
- Developer B: T023, NVIDIA probe tests.
- Developer C: T024, CLI integration and privacy tests.
- Developer D: T025, timing and network-isolation tests.

### User Story 4

- Developer A: T031, public hardware API contracts.
- Developer B: T032, direct selection and VRAM edge cases.

### User Story 5

- Developer A: T037, Python exception contracts.
- Developer B: T038, end-to-end CLI failure contracts.
- After red tests exist, T039 and T040 can be implemented concurrently.

## Implementation Strategy

### MVP First

The suggested MVP is Setup + Shared Foundation + User Story 1:

1. Complete T001-T003.
2. Complete T004-T007 with observed red-green evidence.
3. Complete T008-T015 with tests before implementation.
4. Stop and validate local wheel/sdist installation, package import, version, and root help.

This MVP proves that the repository is a real local package but intentionally does not claim that
the full diagnostic is complete.

### Incremental Delivery

1. Add US3 to establish stable configuration.
2. Add US2 to deliver the complete diagnostic and private hardware probe.
3. Add US4 to expose the direct public hardware API.
4. Add US5 to harden every public failure path.
5. Complete cross-cutting quality gates and optional reference-GPU validation.

No increment publishes to public PyPI; PRD-02 owns the first public release.

## Notes

- `[P]` means file-level parallelism after explicit prerequisites, not permission to ignore TDD.
- Every source task includes English docstrings required by constitution version 1.0.0.
- Every CLI task preserves complete English help and executable examples.
- `uv` is the only project environment, dependency, build, and future publication tool.
- Hosted CI uses mocks for NVIDIA; a real GPU check is recorded separately when available.
- Stop at any checkpoint to validate the corresponding user story independently.
