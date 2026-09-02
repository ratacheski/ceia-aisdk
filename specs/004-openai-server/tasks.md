---

description: "Implementation tasks for the CEIA AI SDK OpenAI-compatible local server"

---

# Tasks: OpenAI-Compatible Local Server

**Input**: Design documents from `specs/004-openai-server/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`,
`quickstart.md`, and constitution version 1.0.0

**Tests**: Mandatory. Every behavior task follows red-green-refactor: write and run the listed
test first, verify that it fails for the expected reason, then implement the minimum behavior.

**Organization**: Tasks are grouped by user story. P0 stories (US1–US4, US6) plus packaging
prep are the `0.2.0` gate. US7 (adaptive embeddings/audio/vision) MUST NOT block that gate.
US5 (publish) is last and MUST wait for the P0 stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel after its explicit prerequisites because it changes different
  files.
- **[Story]**: Maps the task to a user story from `spec.md`.
- Every task names the exact file or files it changes or validates.

## Phase 1: Setup

**Purpose**: Declare the `[server]` extra, bump the development version, and add the server
package layout.

- [X] T001 Add `fastapi>=0.115` and `uvicorn>=0.32` to `[project.optional-dependencies] server`
      with `uv add --optional server`, add the official `openai` client as a dev dependency,
      set `project.version` to `0.2.0.dev0` in `pyproject.toml`, and commit the lock in
      `pyproject.toml` and `uv.lock`
- [X] T002 [P] Create the server package skeleton with English module docstrings in
      `src/ceia_aisdk/server/__init__.py`, `src/ceia_aisdk/server/app.py`,
      `src/ceia_aisdk/server/openai_compat.py`, `src/ceia_aisdk/server/adaptive.py`,
      `src/ceia_aisdk/server/pool.py`, and `src/ceia_aisdk/server/messages.py`
- [X] T003 [P] Update the existing extra assertion in
      `tests/contract/test_package_api.py` so `server` is expected as a declared extra (the
      current `assert "server" not in extras` must fail after T001 and then be rewritten)

**Checkpoint**: `uv lock --check` and `uv sync --locked --all-groups --all-extras` succeed.
`import ceia_aisdk` still does not load FastAPI, uvicorn, or `llama_cpp`.

---

## Phase 2: Foundational Shared Contracts

**Purpose**: `ServerError`, import budget, `create_app` factory, CLI `serve` discovery, doctor
extras, and the HTTP error envelope that every story uses.

**Critical**: No user-story implementation begins until these tests have failed and the shared
contracts pass.

### Tests First

- [X] T004 [P] Write and run failing `ServerError` hierarchy, nonempty remediation, and
      English docstring tests in `tests/contract/test_public_errors.py`
- [X] T005 [P] Write and run failing tests that `import ceia_aisdk` leaves `fastapi` and
      `uvicorn` out of `sys.modules` and does not import `ceia_aisdk.server` in
      `tests/contract/test_server_import_budget.py`
- [X] T006 [P] Write and run failing root-help `serve` discovery and
      `ceia-aisdk serve --help` completeness tests (flags, defaults `127.0.0.1`/`11434`,
      extra requirement, executable `serve --help` example, skip long-running `serve` in the
      example harvester) in `tests/contract/test_serve_cli_help.py` and extend
      `tests/contract/test_cli_help.py`
- [X] T007 [P] Write and run failing doctor `optional_groups` includes `server` tests in
      `tests/unit/test_diagnostics.py` and `tests/integration/test_doctor.py`

### Minimal Implementation

- [X] T008 [P] Implement documented `ServerError` in `src/ceia_aisdk/errors.py` and re-export
      it from `src/ceia_aisdk/__init__.py` without importing `ceia_aisdk.server`
- [X] T009 Implement `create_app` (no socket bind, no `LLM` construct, no `llama_cpp` load)
      and the stable JSON error envelope helper in `src/ceia_aisdk/server/app.py` and export
      `create_app` from `src/ceia_aisdk/server/__init__.py`
- [X] T010 Register `ceia-aisdk serve` in `src/ceia_aisdk/cli.py` with `--host`, `--port`,
      `--token`, `--cors`, `--debug`, English help, and lazy import of the server stack so
      `--help` works without FastAPI
- [X] T011 List declared extras (including `server`) from distribution metadata in
      `src/ceia_aisdk/_diagnostics.py`
- [X] T012 Run and pass `tests/contract/test_public_errors.py`,
      `tests/contract/test_server_import_budget.py`, `tests/contract/test_serve_cli_help.py`,
      `tests/contract/test_cli_help.py`, `tests/unit/test_diagnostics.py`, and
      `tests/integration/test_doctor.py`

**Checkpoint**: `serve --help` works without the extra. Package import stays free of FastAPI.
Doctor lists `server`. User-story work can start.

---

## Phase 3: User Story 1 — Start a Local OpenAI-Compatible Server (Priority: P1) 🎯 MVP

**Goal**: `ceia-aisdk serve` binds `127.0.0.1:11434` by default, logs an absolute `/v1` URL,
explains the extra when FastAPI/uvicorn are missing, and fails fast with `--port` remediation
when the port is taken.

**Independent Test**: Start with the extra and confirm the ready log URL. Run without the extra
and get `ServerError` mentioning `ceia-aisdk[server]`. Occupy the port and get bind remediation.

### Tests First

- [X] T013 [P] [US1] Write and run failing missing-extra start tests (no traceback, remediation
      names `ceia-aisdk[server]`) in `tests/unit/test_server_missing_extra.py`
- [X] T014 [P] [US1] Write and run failing default-bind, `--host`/`--port` override, ready-log
      absolute URL, and occupied-port `ServerError` tests in
      `tests/integration/test_serve_bind.py`

### Minimal Implementation

- [X] T015 [US1] Implement missing-extra detection and `ServerError` in the `serve` command
      body in `src/ceia_aisdk/cli.py`
- [X] T016 [US1] Implement uvicorn bind, default `127.0.0.1:11434`, ready INFO log with
      `http://<host>:<port>/v1`, bind-failure `ServerError` (mentions `--port` and stopping
      the occupant), and no message-body logging unless `--debug` in `src/ceia_aisdk/cli.py`
      and `src/ceia_aisdk/server/app.py`
- [X] T017 [US1] Run and make the US1 suite pass through `uv` for
      `tests/unit/test_server_missing_extra.py`, `tests/integration/test_serve_bind.py`,
      `tests/contract/test_serve_cli_help.py`, and
      `tests/contract/test_server_import_budget.py`

**Checkpoint**: `serve` starts on loopback or fails with remediation. This is the MVP process
demo (no chat yet).

---

## Phase 4: User Story 2 — List Models and Complete Chat (Priority: P1)

**Goal**: `GET /v1/models` returns opaque LLM aliases within 2 s. `POST /v1/chat/completions`
returns nonempty text (plain and SSE) matching shipped `LLM` behavior. An official client or
httpx can complete a chat against `/v1`.

**Independent Test**: ASGI TestClient lists only `llm/<size>` ids, completes non-stream chat,
reads ≥ 1 SSE `data:` chunk, and drives `openai.OpenAI` (or httpx) with
`base_url=.../v1`. Two requests do not persist history.

### Tests First

- [X] T018 [P] [US2] Write and run failing message-translation tests (require `model` and
      `messages`, defaults `temperature=0.8` / `max_tokens=512`, reject `n!=1`, reject vision
      parts) in `tests/unit/test_server_messages.py`
- [X] T019 [P] [US2] Write and run failing `/v1/models` opacity and `/v1/chat/completions`
      nonempty-text tests (tiny GGUF or fake LLM; skip live GGUF explicitly if missing) in
      `tests/integration/test_serve_models_chat.py`
- [X] T020 [P] [US2] Write and run failing SSE `data:` chunk and `[DONE]` tests in
      `tests/integration/test_serve_stream.py`
- [X] T021 [P] [US2] Write and run failing official-client or httpx-ASGI happy-path chat
      tests in `tests/integration/test_serve_openai_client.py`

### Minimal Implementation

- [X] T022 [US2] Implement OpenAI message translation (text roles, defaults, vision detect)
      in `src/ceia_aisdk/server/messages.py`
- [X] T023 [US2] Implement a one-instance-per-alias pool without the waiter cap (lock only)
      in `src/ceia_aisdk/server/pool.py`
- [X] T024 [US2] Implement `GET /v1/models` (catalog `llm/<size>` only, no HF names, no
      `tool_use` claim on aliases that lack it) and text
      `POST /v1/chat/completions` (non-stream + SSE) in
      `src/ceia_aisdk/server/openai_compat.py` and wire routes in
      `src/ceia_aisdk/server/app.py`
- [X] T025 [US2] Map `ModelNotFoundError`, `DownloadError`, `DeviceError`, and
      `GenerationError` to the HTTP envelope (404/503/400, no traceback) in
      `src/ceia_aisdk/server/app.py`
- [X] T026 [US2] Run and make the US2 suite pass through `uv` for
      `tests/unit/test_server_messages.py`, `tests/integration/test_serve_models_chat.py`,
      `tests/integration/test_serve_stream.py`, and
      `tests/integration/test_serve_openai_client.py`

**Checkpoint**: A client can list models and chat. History is not written to disk.

---

## Phase 5: User Story 3 — Keep the Default Bind Surface Local (Priority: P1)

**Goal**: Optional Bearer token (401 when set and missing/wrong). Default CORS allows only
localhost origins. `--cors` relaxes to any origin.

**Independent Test**: Token configured → 401 without Bearer, 200 with the matching token.
Default CORS rejects a foreign origin and allows `http://localhost:3000`. `--cors` allows the
foreign origin.

### Tests First

- [X] T027 [P] [US3] Write and run failing Bearer 401/200 and CORS default/`--cors` tests in
      `tests/integration/test_serve_auth_cors.py`

### Minimal Implementation

- [X] T028 [US3] Implement optional Bearer (`hmac.compare_digest`) and localhost-only CORS
      (`--cors` → any origin, no credentials) in `src/ceia_aisdk/server/app.py` and pass
      `token` / `cors_open` / `debug` from `src/ceia_aisdk/cli.py`
- [X] T029 [US3] Run and make `tests/integration/test_serve_auth_cors.py` pass through `uv`
      without regressing US1/US2

**Checkpoint**: Default bind stays local. Token and CORS match the HTTP contract.

---

## Phase 6: User Story 4 — Queue Overflow Returns a Clear Overload (Priority: P1)

**Goal**: One in-use `LLM` per alias. Process-wide waiter cap 8. Overflow is HTTP 429 with
stable JSON. No conversation files.

**Independent Test**: Fill 8 waiters on a busy alias and assert the next chat is 429. Queued
work still completes. No history files appear under the cache dir.

### Tests First

- [X] T030 [P] [US4] Write and run failing admission-queue unit tests (cap 8, in-flight not
      counted, 9th waiter rejected) in `tests/unit/test_server_pool.py`
- [X] T031 [P] [US4] Write and run failing HTTP 429-after-8-waiters tests in
      `tests/integration/test_serve_queue.py`

### Minimal Implementation

- [X] T032 [US4] Implement the waiter cap of 8 and per-alias lock in
      `src/ceia_aisdk/server/pool.py` and return 429 with `overloaded_error` + remediation
      from `src/ceia_aisdk/server/openai_compat.py`
- [X] T033 [US4] Run and make `tests/unit/test_server_pool.py` and
      `tests/integration/test_serve_queue.py` pass through `uv`

**Checkpoint**: Overload is visible as 429. Instances stay non-concurrent.

---

## Phase 7: User Story 6 — Tool Calls on the Same Chat Route (Priority: P1)

**Goal**: Library `LLM.complete` returns text or structured `tool_calls` without changing
`LLM.chat` → `str`. `/v1/chat/completions` accepts OpenAI `tools`, returns `tool_calls`,
accepts `role: "tool"` follow-up, and streams `delta.tool_calls`. Serve never executes
handlers.

**Independent Test**: Fake-backend `complete` emits `ToolCall`. HTTP returns OpenAI
`tool_calls` then accepts a tool-result turn. Alias without `tool_use` → `CapabilityError` /
400. `LLM.chat` still returns `str`.

### Tests First

- [X] T034 [P] [US6] Write and run failing `ToolCall` / `CompletionResult` / `LLM.complete`
      (text vs tool calls, capability gate, `chat` still `str`) tests in
      `tests/unit/test_llm_tool_calls.py`
- [X] T035 [P] [US6] Write and run failing HTTP `tools` → `tool_calls`, `role: tool`
      follow-up, SSE `delta.tool_calls`, and 400-without-`tool_use` tests in
      `tests/integration/test_serve_tools.py`
- [X] T036 [P] [US6] Extend and run failing public export / signature tests for `complete`,
      `ToolCall`, and `CompletionResult` in `tests/contract/test_llm_api.py`

### Minimal Implementation

- [X] T037 [US6] Add `ToolCall` and `CompletionResult` in `src/ceia_aisdk/llm/tools.py` and
      export them from `src/ceia_aisdk/llm/__init__.py` without loading `llama_cpp`
- [X] T038 [US6] Implement one-step `LLM.complete` (and `AsyncLLM.complete`) that performs
      a single generate, returns text or `tool_calls`, never runs `handler`, and raises
      `CapabilityError` when the alias lacks `tool_use`, in `src/ceia_aisdk/llm/model.py`,
      `src/ceia_aisdk/llm/async_model.py`, and `src/ceia_aisdk/llm/backend.py`
- [X] T039 [US6] Map OpenAI `tools` / `tool_choice` / `role: tool` onto `complete` and emit
      OpenAI `tool_calls` / SSE `delta.tool_calls` in `src/ceia_aisdk/server/messages.py` and
      `src/ceia_aisdk/server/openai_compat.py`
- [X] T040 [US6] Run and make the US6 suite pass through `uv` for
      `tests/unit/test_llm_tool_calls.py`, `tests/integration/test_serve_tools.py`,
      `tests/contract/test_llm_api.py`, and `tests/contract/test_llm_import_budget.py`

**Checkpoint**: Agents can do the OpenAI tool round trip on the same POST. Library `chat`
is unchanged.

---

## Phase 8: User Story 7 — Adaptive Routes for Modules Not in This Slice (Priority: P2)

**Goal**: Reserved embeddings/audio routes return stable 501 while those modules are absent.
Vision image parts in chat return 400. Assistants/batches/files/fine-tune are 404. No
traceback. Must not block `0.2.0`.

**Independent Test**: POST embeddings and audio → 501 JSON. Chat with `image_url` → 400.
Unknown OpenAI product URL → 404. P0 chat and tools still pass.

### Tests First

- [X] T041 [P] [US7] Write and run failing 501 embeddings/audio, 400 vision, and 404
      assistants/batches/files tests in `tests/integration/test_serve_adaptive.py`

### Minimal Implementation

- [X] T042 [US7] Register reserved `/v1/embeddings`, `/v1/audio/transcriptions`, and
      `/v1/audio/speech` as 501, keep vision-part 400 in message translation, and use the
      standard 404 envelope for unimplemented OpenAI product URLs in
      `src/ceia_aisdk/server/adaptive.py`, `src/ceia_aisdk/server/messages.py`, and
      `src/ceia_aisdk/server/app.py`
- [X] T043 [US7] Run and make `tests/integration/test_serve_adaptive.py` pass through `uv`
      without regressing US2/US6

**Checkpoint**: Missing modules fail stably. Chat and tools still work.

---

## Phase 9: User Story 5 — Publish 0.2.0 with the Server Extra (Priority: P1)

**Goal**: Same project on the public index as `ceia-aisdk==0.2.0` with installable `[server]`,
no weights, README serve + tools section, complete CLI help.

**Independent Test**: Metadata declares `server`. Wheel/sdist have `ceia_aisdk.server` and no
`.gguf`. README documents serve, bind, token, CORS, queue 8, tools (client executes), reverse
proxy TLS. Do not `uv publish` until the polish publish task.

### Tests First

- [X] T044 [P] [US5] Write and run failing extra/README/artifact tests (no weights, `[server]`
      declared, serve and tools phrases) in `tests/contract/test_server_packaging.py` and
      extend `tests/integration/test_installed_artifacts.py` if needed

### Minimal Implementation

- [X] T045 [US5] Document `pip install "ceia-aisdk[server]"`, `ceia-aisdk serve`,
      `http://127.0.0.1:11434/v1`, opaque aliases, stream, tools / `tool_calls`, token, CORS,
      queue 8 / 429, port conflict, reverse-proxy TLS, and Linux x86_64 in `README.md`
- [X] T046 [US5] Run and make `tests/contract/test_server_packaging.py` and
      `tests/integration/test_installed_artifacts.py` pass through `uv`

**Checkpoint**: Packaging contract is green. Version is still `0.2.0.dev0` until the publish
task.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, English review, quickstart, and the public `0.2.0` upload.

- [X] T047 [P] Confirm English docstrings (parameters, returns, exceptions, side effects) on
      `create_app`, `ServerError`, `LLM.complete`, `ToolCall`, `CompletionResult`, and server
      modules in `src/ceia_aisdk/server/` and `src/ceia_aisdk/llm/`
- [X] T048 [P] Confirm `ceia-aisdk serve --help` still lists every flag, defaults, constraints,
      loopback warning, extra requirement, and at least one executable example in
      `src/ceia_aisdk/cli.py`
- [X] T049 Run the `specs/004-openai-server/quickstart.md` contributor commands through `uv`
      (`lock --check`, import budget, unit/integration listed there, `ruff`, `pydoclint`,
      `uv build --no-sources`)
- [ ] T050 After gates and the manual serve checklist, set `project.version` to `0.2.0` in
      `pyproject.toml`, run `uv build --no-sources`, inspect artifacts (Twine,
      check-wheel-contents, no weights), and `uv publish` `ceia-aisdk==0.2.0` to public PyPI

**Checkpoint**: `0.2.0` is on the index with `[server]`. US7 must not delay T050 if adaptive
refusals are already merged; if US7 is unfinished, ship P0 without waiting for voice/vision/RAG
implementations (501/400 stubs from T042 are enough).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — MVP process
- **US2 (Phase 4)**: Depends on Foundational; uses `create_app` from Phase 2. Can start after
  US1 or in parallel if `cli.py` bind work is isolated
- **US3 (Phase 5)**: Depends on US2 routes existing (`app.py`)
- **US4 (Phase 6)**: Depends on US2 pool/routes
- **US6 (Phase 7)**: Depends on US2 chat route and the existing `llm` package
- **US7 (Phase 8)**: Depends on US2 routes; MUST NOT block T050
- **US5 (Phase 9)**: Packaging tests can start after T001; README should wait until US1/US2/US6
  behavior is real. `uv publish` is T050 only
- **Polish (Phase 10)**: Depends on desired P0 stories (US1–US4, US6) and US5 packaging tests

### User Story Dependencies

- **US1**: After Phase 2. No other story required
- **US2**: After Phase 2. Needs a listening app (US1 bind optional for ASGI tests)
- **US3**: After US2 (`create_app` routes)
- **US4**: After US2 (`pool.py` + chat handler)
- **US6**: After US2 (same `openai_compat.py` / `messages.py`)
- **US7**: After US2; independent of tools except shared error envelope
- **US5**: Metadata extra after T001; publish after P0

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Types/helpers before routes
- Routes before auth/queue/tools overlays
- Story complete before the next story that edits the same file

### Parallel Opportunities

- T002 and T003 after T001
- T004, T005, T006, T007 in parallel
- T013 and T014 in parallel
- T018–T021 in parallel
- T030 and T031 in parallel
- T034–T036 in parallel
- T047 and T048 in parallel
- US5 packaging tests (T044) can start once the extra exists
- Do not parallelize US2, US3, US4, US6, and US7 on
  `src/ceia_aisdk/server/openai_compat.py` / `app.py` in the same working tree

---

## Parallel Execution Examples

### User Story 1 tests

```bash
uv run pytest tests/unit/test_server_missing_extra.py tests/integration/test_serve_bind.py tests/contract/test_serve_cli_help.py
```

### User Story 2 tests

```bash
uv run pytest tests/unit/test_server_messages.py tests/integration/test_serve_models_chat.py tests/integration/test_serve_stream.py tests/integration/test_serve_openai_client.py
```

### User Story 6 tests

```bash
uv run pytest tests/unit/test_llm_tool_calls.py tests/integration/test_serve_tools.py tests/contract/test_llm_api.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `ceia-aisdk serve` ready log shows `http://127.0.0.1:11434/v1`
5. Continue to US2 before claiming an OpenAI-compatible product

### Incremental Delivery

1. Setup + Foundational
2. US1 serve / bind / missing extra → process MVP
3. US2 models + chat + SSE
4. US3 token + CORS
5. US4 queue 429
6. US6 library `complete` + HTTP tool calls
7. US7 adaptive 501/400 (do not hold publish if only stubs remain)
8. US5 README/packaging
9. Polish + `uv publish` `0.2.0`

### Parallel Team Strategy

After Phase 2:

- Developer A: US1 then US2 then US4 then US6 (critical path on `cli.py` / `openai_compat.py` /
  `llm/model.py`)
- Developer B: US3 auth/CORS after US2 merges `app.py`
- Developer C: US5 README/packaging tests and US7 adaptive stubs (different files once routes
  exist)

Do not parallelize US2 and US6 on `messages.py` / `openai_compat.py` in the same working tree.

---

## Notes

- [P] tasks change different files and have no unmet dependencies.
- Never download production `llm/small` in default CI. Reuse
  `scripts/fetch-llm-test-fixture.sh` and `CEIA_AISDK_CATALOG`. Tool-call shape uses a fake
  backend or recording when the tiny GGUF cannot emit tools.
- Verify tests fail before implementing.
- Commit after each task or logical group.
- Stop at any checkpoint to validate the story independently.
- Do not run `uv publish` before T050. US7 must not delay T050.
- Serve does not execute tool handlers. `LLM.chat` must remain `str`.
- Live bind tests may enable loopback sockets; ASGI TestClient tests stay socket-free.
