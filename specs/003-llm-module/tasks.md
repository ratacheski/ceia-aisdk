---

description: "Implementation tasks for the CEIA AI SDK local LLM module and first public release"
---

# Tasks: Local LLM Module and First Public Release

**Input**: Design documents from `specs/003-llm-module/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`,
`quickstart.md`, and constitution version 1.0.0

**Tests**: Mandatory. Every behavior task follows red-green-refactor: write and run the listed
test first, verify that it fails for the expected reason, then implement the minimum behavior.

**Organization**: Tasks are grouped by user story. P0 stories (US1–US4) are the `0.1.0` gate.
P1 stories (US5–US6) are designed into the same release. US7 (tool use) MUST NOT block
first-chat or the public upload.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel after its explicit prerequisites because it changes different
  files.
- **[Story]**: Maps the task to a user story from `spec.md`.
- Every task names the exact file or files it changes or validates.

## Phase 1: Setup

**Purpose**: Add the inference runtime, LLM package layout, and shared test fixtures.

- [X] T001 Add `llama-cpp-python` as a runtime dependency with `uv add`, declare the `[cuda]`
      extra in `pyproject.toml`, and commit the lock in `pyproject.toml` and `uv.lock`
- [X] T002 [P] Create the LLM package skeleton with English module docstrings in
      `src/ceia_aisdk/llm/__init__.py`, `src/ceia_aisdk/llm/settings.py`,
      `src/ceia_aisdk/llm/model.py`, `src/ceia_aisdk/llm/async_model.py`,
      `src/ceia_aisdk/llm/session.py`, `src/ceia_aisdk/llm/backend.py`, and
      `src/ceia_aisdk/llm/devices.py`
- [X] T003 [P] Add `scripts/fetch-llm-test-fixture.sh` (pinned tiny GGUF URL and checksum),
      ignore `tests/fixtures/` binaries in `.gitignore` if needed, and add loopback-catalog,
      isolated `cache_dir`, fake-backend, and skip-if-missing-fixture helpers in
      `tests/conftest.py`

**Checkpoint**: `uv lock --check` and `uv sync --locked --all-groups --all-extras` succeed.
`import ceia_aisdk` still does not load `llama_cpp`.

---

## Phase 2: Foundational Shared Contracts

**Purpose**: Public errors, `[llm]` settings, lazy backend protocol, and import budget that
every story uses.

**Critical**: No user-story implementation begins until these tests have failed and the shared
contracts pass.

### Tests First

- [X] T004 [P] Write and run failing `GenerationError` and `CapabilityError` hierarchy,
      nonempty remediation, and English docstring tests in
      `tests/contract/test_public_errors.py`
- [X] T005 [P] Write and run failing `LLMSettings` default, TOML `[llm]`, environment
      `CEIA_AISDK_LLM_*`, explicit-argument, and invalid-value tests in
      `tests/unit/test_llm_settings.py`
- [X] T006 [P] Write and run failing tests that `import ceia_aisdk` and
      `from ceia_aisdk.llm import LLM` leave `llama_cpp` out of `sys.modules` in
      `tests/contract/test_llm_import_budget.py` and extend
      `tests/contract/test_package_api.py`

### Minimal Implementation

- [X] T007 [P] Implement documented `GenerationError` and `CapabilityError` in
      `src/ceia_aisdk/errors.py` and re-export them from `src/ceia_aisdk/__init__.py` without
      importing `ceia_aisdk.llm`
- [X] T008 Implement `LLMSettings` load/precedence/validation in
      `src/ceia_aisdk/llm/settings.py` per `specs/003-llm-module/contracts/configuration.md`
- [X] T009 Implement the private backend protocol with lazy `llama_cpp` import (module-level
      import forbidden) in `src/ceia_aisdk/llm/backend.py`
- [X] T010 Export `LLMSettings` from `src/ceia_aisdk/llm/__init__.py` without importing
      `llama_cpp`, then run and pass `tests/contract/test_public_errors.py`,
      `tests/unit/test_llm_settings.py`, `tests/contract/test_llm_import_budget.py`, and
      `tests/contract/test_package_api.py`

**Checkpoint**: Settings resolve without constructing a model. Package and LLM-type imports
remain free of `llama_cpp`.

---

## Phase 3: User Story 1 — First Chat with Zero Configuration (Priority: P1) 🎯 MVP

**Goal**: `LLM()` defaults to `llm/small@latest`, obtains the local file through `ensure_local`,
and `chat` returns a nonempty string. Offline cache miss is a fast `DownloadError`.

**Independent Test**: Construct `LLM()` against the fixture catalog, call
`chat("Say only: ok")`, confirm a nonempty `str`, progress callback on a TTY, and offline miss
within 1 second without loading `llama_cpp`.

### Tests First

- [X] T011 [P] [US1] Write and run failing constructor, default-alias, `LLM("medium")` domain
      context, `device=` override, and not-thread-safe docstring contract tests in
      `tests/contract/test_llm_api.py`
- [X] T012 [P] [US1] Write and run failing fake-backend chat, TTY progress-to-`ensure_local`,
      and unqualified-size tests in `tests/unit/test_llm_construct.py`
- [X] T013 [P] [US1] Write and run failing real-backend nonempty-chat tests (skip explicitly
      when the tiny GGUF is absent) in `tests/integration/test_llm_chat.py`
- [X] T014 [P] [US1] Write and run failing offline cache-miss ≤ 1 s `DownloadError` tests that
      assert `llama_cpp` stays unloaded in `tests/integration/test_llm_offline.py`

### Minimal Implementation

- [X] T015 [US1] Implement effective-device CPU/`auto` selection without VRAM fallback in
      `src/ceia_aisdk/llm/devices.py`
- [X] T016 [US1] Implement `LLM.__init__` (settings, `resolve`/`ensure_local` with TTY
      progress, lazy backend) in `src/ceia_aisdk/llm/model.py`
- [X] T017 [US1] Implement `LLM.chat` (default `max_tokens=512`) and public `alias`/`device`
      properties in `src/ceia_aisdk/llm/model.py`, export `LLM` from
      `src/ceia_aisdk/llm/__init__.py` with a not-thread-safe English docstring
- [X] T018 [US1] Run and make the US1 suite pass through `uv` for
      `tests/contract/test_llm_api.py`, `tests/unit/test_llm_construct.py`,
      `tests/integration/test_llm_chat.py`, `tests/integration/test_llm_offline.py`, and
      `tests/contract/test_llm_import_budget.py`

**Checkpoint**: Zero-config chat works on the tiny fixture. `import ceia_aisdk` still does not
load `llama_cpp`. This is the MVP demo.

---

## Phase 4: User Story 2 — Streaming and Multi-Turn Session (Priority: P1)

**Goal**: `.stream` yields string chunks and `.session` retains history across two sends.

**Independent Test**: Compare stream concatenation to chat under `temperature=0` and a fixed
seed (or the documented nonempty-chunk fallback). Send two session turns and assert history is
retained (unit) plus a best-effort fixture integration.

### Tests First

- [X] T019 [P] [US2] Write and run failing session history and context-overflow
      `GenerationError` tests in `tests/unit/test_llm_session.py`
- [X] T020 [P] [US2] Write and run failing stream iterator / concatenation tests in
      `tests/integration/test_llm_stream_session.py`
- [X] T021 [P] [US2] Extend and run failing `stream`/`session` signature and docstring tests
      in `tests/contract/test_llm_api.py`

### Minimal Implementation

- [X] T022 [US2] Implement `Session.send` / `Session.stream` and message retention in
      `src/ceia_aisdk/llm/session.py`
- [X] T023 [US2] Implement `LLM.stream` and `LLM.session` in `src/ceia_aisdk/llm/model.py` and
      export `Session` from `src/ceia_aisdk/llm/__init__.py`
- [X] T024 [US2] Run and make the US2 suite pass through `uv` for
      `tests/unit/test_llm_session.py`, `tests/integration/test_llm_stream_session.py`, and
      `tests/contract/test_llm_api.py`

**Checkpoint**: Stream and session work on CPU. Thread-safety remains documentation-only (no
global lock).

---

## Phase 5: User Story 3 — GPU Extra Without Manual Runtime Flags (Priority: P1)

**Goal**: `[cuda]` extra is installable and documented; `doctor` reports CUDA binding vs GPU
visibility; `device="cpu"` forces CPU; post-start OOM is `DeviceError`.

**Independent Test**: `ceia-aisdk doctor` copy block includes `cuda_binding=yes|no`. Forced CPU
chat works with a fake or real backend. Explicit CUDA without binding raises `DeviceError`.
Live NVIDIA generation is a reference-machine checklist, not a required CI job.

### Tests First

- [X] T025 [P] [US3] Write and run failing `cuda_binding` copy-block, help-text, and
      `optional_groups` no-longer-`cuda:reserved` tests in `tests/unit/test_diagnostics.py`,
      `tests/integration/test_doctor.py`, and `tests/contract/test_cli_help.py`
- [X] T026 [P] [US3] Write and run failing forced-CPU, missing-binding, and explicit-CUDA
      `DeviceError` tests in `tests/unit/test_llm_devices.py` and
      `tests/integration/test_llm_device_cpu.py`
- [X] T027 [P] [US3] Write and run failing OOM-wrapping `DeviceError` remediation tests
      (`llm/small` or `device="cpu"`) in `tests/unit/test_llm_devices.py`

### Minimal Implementation

- [X] T028 [US3] Extend device selection for CUDA binding presence, `n_gpu_layers` 0 vs `-1`,
      and explicit-CUDA failures in `src/ceia_aisdk/llm/devices.py`
- [X] T029 [US3] Add the CLI-only `llama_cpp` capability probe and `cuda_binding` field in
      `src/ceia_aisdk/_diagnostics.py` without importing it from
      `src/ceia_aisdk/__init__.py`
- [X] T030 [US3] Map backend out-of-memory to `DeviceError` in `src/ceia_aisdk/llm/backend.py`
      and log a `cuda` token on GPU generation in `src/ceia_aisdk/llm/model.py`
- [X] T031 [US3] Run and make the US3 suite pass through `uv` for
      `tests/unit/test_diagnostics.py`, `tests/integration/test_doctor.py`,
      `tests/contract/test_cli_help.py`, `tests/unit/test_llm_devices.py`, and
      `tests/integration/test_llm_device_cpu.py`

**Checkpoint**: Doctor distinguishes GPU visible from binding present. Forced CPU works. CUDA
compile remains outside the 15-minute KPI. Live GPU chat stays on the reference checklist.

---

## Phase 6: User Story 4 — Publish 0.1.0 Packaging Readiness (Priority: P1)

**Goal**: README, classifiers, extra docs, and artifacts are ready for public `0.1.0`. The
actual index upload waits until US5 and US6 (same-release P1) finish; US7 must not block it.

**Independent Test**: `uv build` wheel/sdist contain `ceia_aisdk.llm` and no `.gguf`. README
contains the 15-minute `pip install` quickstart and Linux-only language. Version remains
`0.1.0.dev0` until the polish publish task.

### Tests First

- [X] T032 [P] [US4] Write and run failing wheel/sdist content, no-weight, Linux-classifier,
      and `[cuda]` extra-name tests in `tests/contract/test_llm_packaging.py` and extend
      `tests/integration/test_installed_artifacts.py`
- [X] T033 [P] [US4] Write and run failing README phrase tests (15-minute path, `llm/small`,
      not thread-safe, Linux x86_64, weights not in the wheel, `[cuda]` extra) in
      `tests/contract/test_llm_packaging.py`

### Minimal Implementation

- [X] T034 [US4] Rewrite the project page in `README.md` per
      `specs/003-llm-module/contracts/packaging.md` (end-user `pip`, contributor `uv`)
- [X] T035 [US4] Update package description, `[cuda]` extra notes, and
      `check-wheel-contents` configuration in `pyproject.toml`
- [X] T036 [US4] Run and make the US4 suite pass through `uv` for
      `tests/contract/test_llm_packaging.py` and
      `tests/integration/test_installed_artifacts.py`

**Checkpoint**: Packaging is publish-ready. Do **not** run `uv publish` yet.

---

## Phase 7: User Story 5 — Automatic Memory Fallback Before Generation (Priority: P2)

**Goal**: `device="auto"` plus `size_gb > 0.9 * free VRAM` selects CPU, logs `WARNING`, and
still chats. Explicit CUDA never silent-falls-back.

**Independent Test**: Fake snapshot with oversized `size_gb` yields CPU + WARNING; sufficient
VRAM stays CUDA; explicit `cuda` raises `DeviceError`.

### Tests First

- [X] T037 [P] [US5] Write and run failing 90% margin, sufficient-VRAM, and explicit-CUDA
      no-fallback tests in `tests/unit/test_llm_devices.py`

### Minimal Implementation

- [X] T038 [US5] Implement the 0.9 free-memory fallback and WARNING in
      `src/ceia_aisdk/llm/devices.py` and wire it from `src/ceia_aisdk/llm/model.py`
- [X] T039 [US5] Run and make `uv run pytest tests/unit/test_llm_devices.py` pass

**Checkpoint**: Auto devices fall back before generation; explicit CUDA still errors.

---

## Phase 8: User Story 6 — Mirrored Async Chat (Priority: P2)

**Goal**: `AsyncLLM` mirrors chat/stream/session using executor offload. Document the blocking
binding.

**Independent Test**: Await `AsyncLLM.chat` under an asyncio timeout against the fake or tiny
backend; confirm `llama_cpp` still does not load on `from ceia_aisdk.llm import AsyncLLM`.

### Tests First

- [X] T040 [P] [US6] Write and run failing async smoke, timeout, and import-budget tests in
      `tests/integration/test_async_llm.py` and `tests/contract/test_llm_import_budget.py`
- [X] T041 [P] [US6] Extend and run failing `AsyncLLM` signature/docstring tests in
      `tests/contract/test_llm_api.py`

### Minimal Implementation

- [X] T042 [US6] Implement `AsyncLLM` and async session with `asyncio.to_thread` (or
      equivalent) and English binding-limitation docs in
      `src/ceia_aisdk/llm/async_model.py`
- [X] T043 [US6] Export `AsyncLLM` from `src/ceia_aisdk/llm/__init__.py` without importing
      `llama_cpp` at import time
- [X] T044 [US6] Run and make the US6 suite pass through `uv` for
      `tests/integration/test_async_llm.py`, `tests/contract/test_llm_api.py`, and
      `tests/contract/test_llm_import_budget.py`

**Checkpoint**: At least one `AsyncLLM` smoke test exists for `0.1.0`.

---

## Phase 9: User Story 7 — Tool Use (Priority: P3, MUST NOT block 0.1.0)

**Goal**: OpenAI-ish tools API with a capability gate. First-chat merge and `0.1.0` upload MUST
NOT wait on this phase.

**Independent Test**: Passing tools to an alias without `tool_use` raises `CapabilityError`. A
`get_weather` loop test uses a capable alias, a recording, or an explicit English skip.

### Tests First

- [X] T045 [P] [US7] Write and run failing capability-gate tests in
      `tests/unit/test_llm_capabilities.py`
- [X] T046 [P] [US7] Write the `get_weather` loop test or explicit skip in
      `tests/integration/test_llm_chat.py` or `tests/unit/test_llm_capabilities.py`

### Minimal Implementation

- [X] T047 [US7] Implement `ToolDeclaration` and the `tools=` constructor gate in
      `src/ceia_aisdk/llm/model.py` (and types exported from
      `src/ceia_aisdk/llm/__init__.py`) per `specs/003-llm-module/contracts/tools.md`
- [X] T048 [US7] Run and make `uv run pytest tests/unit/test_llm_capabilities.py` pass

**Checkpoint**: Tools are gated. Skip or defer the live loop without blocking publish.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Documentation completeness, quality gates, optional performance evidence, and the
public `0.1.0` upload after US1–US6.

- [X] T049 [P] Add remaining English docstrings (parameters, returns, exceptions, side
      effects, not-thread-safe) on every public LLM type and method in
      `src/ceia_aisdk/llm/` and verify with `uv run pydoclint src`
- [X] T050 [P] Add the opt-in warm first-token test (skip in default CI) in
      `tests/performance/test_llm_first_token.py`
- [X] T051 Confirm `doctor` still completes within 5 seconds and opens zero sockets in
      `tests/performance/test_doctor_timing.py` and `tests/integration/test_doctor.py`
- [X] T052 Confirm prompts/completions are not logged at WARNING/ERROR and that no telemetry
      client is introduced in `src/ceia_aisdk/llm/`
- [X] T053 Run contributor quality gates through `uv`: `uv lock --check`, `uv run ruff check
      src tests`, `uv run ruff format --check src tests`, `uv run pydoclint src`,
      `uv run pytest`, `uv build --no-sources`
- [X] T054 Execute the automated sections of `specs/003-llm-module/quickstart.md`
- [X] T055 Complete the manual CPU first-chat checklist in
      `specs/003-llm-module/quickstart.md` section 8 on the reference Linux x86_64 machine
      (15-minute path; CUDA compile excluded)
- [X] T056 Set `project.version` to `0.1.0` in `pyproject.toml`, rebuild, inspect artifacts
      with Twine and `check-wheel-contents`, and publish with `uv publish` per
      `specs/003-llm-module/contracts/packaging.md`
- [X] T057 Verify `ceia-aisdk==0.1.0` on the public index and that the project page matches
      the README quickstart (Linux only, no Windows promise, no weights in the files)

**Checkpoint**: Public product exists. US7 may still be unfinished.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — MVP
- **US2 (Phase 4)**: Depends on US1 (`LLM` in `model.py`)
- **US3 (Phase 5)**: Doctor diagnostics can start after Foundational in parallel with US1
      (`_diagnostics.py`). CUDA generation wiring depends on US1 `LLM`
- **US4 (Phase 6)**: Packaging/README after US1; upload waits for US5 and US6
- **US5 (Phase 7)**: Depends on US3 device selection
- **US6 (Phase 8)**: Depends on US1/US2 surfaces
- **US7 (Phase 9)**: Independent after Foundational; MUST NOT block T056
- **Polish (Phase 10)**: After US1–US6; US7 optional

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no other stories
- **US2 (P1)**: After US1 — same `model.py`
- **US3 (P1)**: Doctor files parallel with US1; `devices.py`/`backend.py` after US1
- **US4 (P1)**: README/packaging after US1; `uv publish` after US6
- **US5 (P2)**: After US3 device rules
- **US6 (P2)**: After US1 (chat) and preferably US2 (stream/session)
- **US7 (P3)**: After Phase 2; do not hold T056

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Settings/devices before `LLM`
- `LLM.chat` before stream/session/async
- Story complete before the next P0 story in the same working tree

### Parallel Opportunities

- T002 and T003 after T001
- T004, T005, T006 after Phase 1
- T007 parallel with T008/T009 after tests exist
- US1 test files T011–T014 in parallel
- US3 doctor tests (T025) in parallel with US1 implementation if staffed
- T032/T033, T040/T041, T045/T046 in parallel within their phases
- T049 and T050 in parallel

Do not parallelize US1 and US2 on `src/ceia_aisdk/llm/model.py` in the same working tree.

---

## Parallel Execution Examples

### User Story 1 tests

```bash
uv run pytest tests/contract/test_llm_api.py tests/contract/test_llm_import_budget.py tests/integration/test_llm_chat.py tests/integration/test_llm_offline.py
```

### User Story 3 doctor vs device tests

```bash
uv run pytest tests/unit/test_diagnostics.py tests/integration/test_doctor.py tests/contract/test_cli_help.py
uv run pytest tests/unit/test_llm_devices.py tests/integration/test_llm_device_cpu.py
```

### User Story 6 tests

```bash
uv run pytest tests/integration/test_async_llm.py tests/contract/test_llm_api.py tests/contract/test_llm_import_budget.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `LLM().chat("Say only: ok")` on the tiny fixture returns a nonempty
   string
5. Continue to US2 before claiming a real chat product

### Incremental Delivery

1. Setup + Foundational
2. US1 first chat → MVP
3. US2 stream/session
4. US3 CUDA extra + doctor binding
5. US4 packaging/README
6. US5 VRAM fallback
7. US6 AsyncLLM
8. Polish + `uv publish` `0.1.0`
9. US7 tools whenever ready (does not hold step 8)

### Parallel Team Strategy

After Phase 2:

- Developer A: US1 then US2 then US6 (critical path on `model.py` / `async_model.py`)
- Developer B: US3 doctor + `_diagnostics.py` (merge before CUDA generation wiring)
- Developer C: US4 README/packaging tests (files under `README.md` and `tests/contract/`)

Do not parallelize US5 and US3 on `devices.py` in the same working tree.

---

## Notes

- [P] tasks change different files and have no unmet dependencies.
- Never download production `llm/small` (2.3 GiB) in default CI. Use
  `scripts/fetch-llm-test-fixture.sh` and `CEIA_AISDK_CATALOG`.
- Verify tests fail before implementing.
- Commit after each task or logical group.
- Stop at any checkpoint to validate the story independently.
- Do not run `uv publish` before T056. US7 must not delay T056.
- CUDA live inference is a reference-machine checklist item, not a required GitHub Actions job.
