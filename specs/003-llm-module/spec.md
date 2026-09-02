# Feature Specification: Local LLM Module and First Public Release

**Feature Branch**: `main` (no branch was created; there is no `before_specify` hook)

**Created**: 2026-09-01

**Status**: Draft

**Input**: PRD-02 (`docs/prd/02-llm.md`) and decisions ratified in the PRD program on 2026-09-01

## User Scenarios & Testing *(mandatory)*

This feature has two delivery bands. **P0** (SpecKit P1 stories) is the gate for the first public product: a developer can install from the public index, run a default local chat, stream, keep a short session, and use a GPU extra on a reference NVIDIA machine. **P1** (SpecKit P2 and P3 stories) may ship in `0.1.0` or in the first patch: mirrored async chat, pre-generation memory fallback, and tool use. Tool use **must not** block the first-chat merge or the `0.1.0` upload.

### User Story 1 - First Chat with Zero Configuration (Priority: P1)

As a developer who discovered the package on the public index, I want to instantiate `LLM()` and call `.chat` so that I can validate the SDK in minutes without choosing a model, a device, or a download URL.

**Why this priority**: The public product exists only when this path returns a local response. Foundations and the registry remain invisible infrastructure until first chat works.

**Independent Test**: On a clean Linux x86_64 CPU machine with working network, install from the public index, run `LLM().chat` with the smoke prompt, and confirm a nonempty string, the default small alias, progress on a TTY, and an offline cache-miss failure.

**Acceptance Scenarios**:

1. **Given** a clean Linux x86_64 CPU machine with a supported Python version and working network, **When** a developer installs `ceia-aisdk` from the public index and runs `LLM().chat("Say only: ok")`, **Then** the call uses the launch default `llm/small@latest`, obtains the local copy through the registry if needed, and returns a nonempty string, all within 15 minutes including the small-model pull.
2. **Given** no alias argument, **When** `LLM()` is constructed, **Then** the launch default is `llm/small@latest`, not `medium`.
3. **Given** `~/.ceia-aisdk/config.toml` with `[llm] default_alias = "medium"`, or an explicit `LLM("medium")`, **When** chat is invoked, **Then** the medium alias is used and remains a valid, supported choice.
4. **Given** first use of an uncached default alias on an interactive terminal, **When** the local copy is obtained, **Then** the developer sees a progress indication for that obtain step.
5. **Given** offline mode enabled and a cache miss for the requested alias, **When** `LLM` construction or the first chat is attempted, **Then** the failure is `DownloadError` with nonempty remediation, occurs within 1 second, and does not hang waiting for a network response.
6. **Given** that only `ceia_aisdk` is imported, **When** no LLM surface import or inference call has occurred, **Then** the local inference backend is not loaded. Loading MAY occur on `from ceia_aisdk.llm import LLM` or on the first inference call; it MUST NOT occur on the top-level package import.

---

### User Story 2 - Streaming and Multi-Turn Session (Priority: P1)

As a developer, I want streaming tokens and a session that remembers prior turns so that the SDK can support a real chat, not only a one-shot string.

**Why this priority**: First chat proves the product; stream and session prove it is usable as a conversation component. Both are P0 for `0.1.0`.

**Independent Test**: With a resident small model on CPU, compare `.chat` and concatenated `.stream` under a fixed seed and temperature (or the documented non-bit-stable fallback), then run a two-turn session fixture that requires memory of the first turn.

**Acceptance Scenarios**:

1. **Given** a constructed `LLM` with a local model, **When** the developer calls `.stream(prompt)`, **Then** the result is an iterator of strings; concatenation equals the `.chat` content under the same fixed seed and temperature in the test, or, if the backend is documented as not bit-stable, the test observes at least one chunk and nonempty final text.
2. **Given** `LLM().session(system=...)`, **When** the developer sends a short factual first turn and then a second turn that depends on it, **Then** the second reply demonstrates awareness of the first (coreference or recalled fact in a fixed fixture).
3. **Given** the public `LLM` class and its documentation, **When** a developer reads the docstring and user documentation, **Then** both state that an instance is not thread-safe.
4. **Given** `llm/small` already resident in memory on CPU, **When** the developer calls `.chat` or consumes the first token from `.stream`, **Then** the first token appears within 10 seconds.

---

### User Story 3 - GPU Extra Without Manual Runtime Flags (Priority: P1)

As a developer with NVIDIA hardware, I want to install the `[cuda]` extra so that inference uses the GPU without selecting backend compile flags.

**Why this priority**: Real CUDA inference is a quality gate for the first public release. It is not part of the 15-minute CPU anchor KPI, and CUDA compilation time must not be counted in that clock.

**Independent Test**: Install `ceia-aisdk[cuda]` on the reference NVIDIA machine, run `doctor`, run `LLM().chat` with `device="auto"` and with forced `device="cpu"`, and exercise an out-of-memory path.

**Acceptance Scenarios**:

1. **Given** a reference NVIDIA GPU whose free memory meets the requirement of `llm/small`, and the `[cuda]` extra installed, **When** the developer runs `LLM().chat` with `device="auto"`, **Then** generation uses the CUDA device and the operational log contains `cuda`.
2. **Given** the `[cuda]` extra installed on that machine, **When** the developer runs `ceia-aisdk doctor`, **Then** the diagnostic reports that the CUDA inference binding is present (`yes`), distinct from merely reporting that a GPU is visible.
3. **Given** `device="cpu"` with the extra installed, **When** chat runs, **Then** generation uses CPU even if a GPU is present.
4. **Given** that generation has started and the GPU runs out of memory, **When** the failure is surfaced, **Then** it is `DeviceError` with nonempty remediation that mentions `llm/small` or `device="cpu"`.
5. **Given** that generation has not started and the GPU cannot host the model, **When** the constructor or first call decides the device, **Then** the SDK either raises `DeviceError` with the same class of remediation or falls back to CPU (the pre-generation size-based fallback in User Story 5, if that story is present in the same release).
6. **Given** the 15-minute first-chat measurement, **When** the clock is interpreted, **Then** it covers public-index install, CPU runtime, `llm/small` pull, and first CPU chat; it does **not** include CUDA extra compilation or GPU setup.

---

### User Story 4 - Publish 0.1.0 on the Public Index (Priority: P1)

As an external developer, I want to `pip install ceia-aisdk` without cloning the repository so that the product actually exists outside the team.

**Why this priority**: PRDs 00 and 01 explicitly withheld publication. This feature is the first public upload (`ceia-aisdk==0.1.0`) and the first moment the 15-minute KPI can be measured by a stranger.

**Independent Test**: Inspect the public index page and artifacts for version `0.1.0`, Linux-only classifiers, quickstart copy, installability of the `[cuda]` extra, and absence of model weights in the wheel and source distribution.

**Acceptance Scenarios**:

1. **Given** completion of the P0 stories, **When** the release is published, **Then** `ceia-aisdk==0.1.0` is available on the public index.
2. **Given** the project page for that version, **When** a developer reads it, **Then** it shows the 15-minute quickstart and states Linux x86_64 support; it does not promise Windows support.
3. **Given** a supported Linux x86_64 environment, **When** a developer runs the documented extra install `pip install ceia-aisdk[cuda]`, **Then** the extra is installable from the same project (prebuilt extra artifact if the team can provide one; otherwise compilation documentation of at most 20 lines).
4. **Given** the published wheel and source distribution, **When** their contents are inspected, **Then** they do not include model weight files.
5. **Given** package classifiers and metadata, **When** they are read, **Then** they declare Linux support and MUST NOT claim Windows or other architectures.

---

### User Story 5 - Automatic Memory Fallback Before Generation (Priority: P2)

As a developer on a machine whose GPU is visible but too small for the chosen alias, I want the SDK to choose CPU and warn before generation starts so that first chat still returns a string instead of failing only after allocation.

**Why this priority**: This is a P1 product behavior that may ship in `0.1.0` or the first patch. It improves the CUDA path but does not block first-chat on CPU.

**Independent Test**: Present a cataloged alias whose `size_gb` exceeds 90% of observed free GPU memory, construct `LLM` with `device="auto"`, and confirm CPU is used, a `WARNING` is emitted, and a string is still returned.

**Acceptance Scenarios**:

1. **Given** `device="auto"` and a cataloged alias whose `size_gb` is greater than 90% of currently free GPU memory, **When** `LLM` is constructed or first generation is requested, **Then** the effective device is CPU, a `WARNING` is logged, and chat still returns a nonempty string.
2. **Given** `device="auto"` and free GPU memory sufficient for the alias under the same 90% margin, **When** the `[cuda]` extra and a usable GPU are present, **Then** the effective device remains CUDA and no memory-fallback `WARNING` is required.
3. **Given** explicit `device="cuda"` or `device="cuda:N"` when the alias does not fit, **When** generation cannot start, **Then** the failure is `DeviceError` with nonempty remediation. Size-based CPU fallback applies only to `device="auto"`; an explicit CUDA request MUST NOT silently switch to CPU.

---

### User Story 6 - Mirrored Async Chat (Priority: P2)

As a developer embedding the SDK in asyncio, I want `AsyncLLM` with `.chat`, `.stream`, and sessions so that I can use the same semantics without blocking the event loop beyond what the local binding requires.

**Why this priority**: The program includes mirrored async APIs starting in this feature, but the rollout allows `AsyncLLM` in `0.1.0` or the first patch. It does not block the CPU first-chat merge.

**Independent Test**: Construct `AsyncLLM`, await `.chat`, consume `.stream`, and run a two-turn async session under an asyncio timeout; cover at least the same smoke behavior as synchronous chat.

**Acceptance Scenarios**:

1. **Given** `AsyncLLM` in a release that includes this story, **When** a developer awaits `.chat`, iterates `.stream`, or uses a session, **Then** the semantics match the synchronous class for alias default, local obtain, session memory, and error types.
2. **Given** the token hot path, **When** async generation runs, **Then** the event loop is not blocked beyond what the local inference binding requires; if the binding is blocking, that limitation is documented, and a test using asyncio plus a timeout still completes.
3. **Given** the `0.1.0` test matrix when this story ships in the same release, **When** automated tests run, **Then** at least one `AsyncLLM` test covers the same smoke behavior as synchronous chat.

---

### User Story 7 - Tool Use for Later Server Exposure (Priority: P3)

As a developer, I want to pass tools into chat so that a later server feature can expose tools without inventing a second calling convention.

**Why this priority**: Tool use is P1 in the program and **must not** block the first-chat merge or the `0.1.0` upload. It may ship in `0.1.0` or a later patch.

**Independent Test**: Pass a `get_weather` stub in the documented tool format to a cataloged alias that declares `tool_use`, observe a call-and-result loop (live capable model or fixture/recording); pass tools to an alias without that capability and confirm a clear error.

**Acceptance Scenarios**:

1. **Given** the tools API, **When** a developer passes tools, **Then** the format is the documented OpenAI-ish contract: name, JSON schema, and call → result.
2. **Given** a cataloged alias whose public capabilities include `tool_use` (or a fixture/recording of that alias), **When** a `get_weather` stub is provided, **Then** at least one test demonstrates the tool loop. If the launch default alias is not reliable for tools, the test uses `llm/medium` (or another alias) marked `capabilities: [tool_use]` and remains P1 — it does not block first-chat.
3. **Given** an alias that does not declare `tool_use`, **When** tools are passed, **Then** the SDK raises a clear public error with nonempty remediation rather than ignoring the tools.

---

### Edge Cases

- The requested alias is unknown to the catalog (`ModelNotFoundError` from the registry, not a generic inference failure).
- Offline mode is on and the alias is already cached; chat must proceed without a network attempt.
- Offline mode is on and the alias is not cached; failure must be `DownloadError` within 1 second with no hang.
- First obtain runs with output redirected or in a non-interactive terminal; the operation must still complete, and progress indication may be omitted or reduced but must remain readable.
- `LLM("medium")`, `LLM("llm/medium")`, `LLM("llm/small@2")`, and config `default_alias` disagree; explicit constructor arguments win over the local file.
- The default small model is already resident (warm) versus first load into memory (cold); the 10-second first-token bound applies only to the warm case.
- `device="cuda"` is set but the `[cuda]` extra is not installed, or a GPU is visible while the inference binding has no CUDA support; `doctor` must distinguish those states, and chat must fail with `DeviceError` or documented CPU fallback according to the device setting.
- Multiple GPUs; `device="cuda:N"` must target that index or fail with `DeviceError`.
- Free GPU memory changes between `doctor` and construction; size-based fallback uses the observation at decision time and does not promise a reservation.
- Session history grows toward the configured context length; overflow must fail with an actionable public error or documented truncation, not a silent hang.
- Stream is abandoned before exhaustion (caller stops iterating); the instance remains documented as not reusable across threads and must not corrupt a later sequential call on the same thread beyond what the binding allows.
- Concurrent calls on the same instance from two threads; behavior is undefined except that documentation forbids it — the SDK must not hide the risk behind a silent global lock.
- Smoke prompt returns more than the expected short token budget; tests may cap generation (for example 64 tokens) while still requiring a nonempty string.
- Public index install on a machine without a GPU; CPU first-chat must succeed without the `[cuda]` extra.
- The `[cuda]` extra fails to build on a machine without a compiler; documentation of at most 20 lines must be the remediation when no prebuilt extra artifact exists.
- Prompts and completions must not leave the machine; no content telemetry.
- Import of `ceia_aisdk` in an environment where the inference extra is installed must still not load that backend until the LLM surface is used.

## Requirements *(mandatory)*

### Functional Requirements

P0 requirements (User Stories 1–4) are the `0.1.0` gate. P1 requirements (User Stories 5–7) may ship in `0.1.0` or the first patch; **FR-033** through **FR-035** (tool use) MUST NOT block the first-chat merge.

- **FR-001**: The SDK MUST provide a public `LLM` type importable as `from ceia_aisdk.llm import LLM`.
- **FR-002**: `LLM()` with no alias argument MUST use `llm/small@latest` as the launch default.
- **FR-003**: `LLM("medium")`, `LLM("llm/medium")`, and equivalent cataloged alias forms MUST remain valid.
- **FR-004**: The local configuration file MUST honor `[llm] default_alias` when no alias is passed to the constructor; an explicit constructor alias MUST win.
- **FR-005**: Construction or first use of `LLM` MUST obtain a verified local copy through the registry `ensure_local` contract before generation.
- **FR-006**: `LLM.chat` MUST return a nonempty `str` for the smoke prompt `"Say only: ok"`.
- **FR-007**: First obtain of an uncached alias MUST show progress when running on an interactive terminal.
- **FR-008**: When `AISDKConfig.offline` is true and the alias is not valid in the cache, `LLM` construction or first chat MUST fail within 1 second with `DownloadError` and MUST NOT hang waiting for the network.
- **FR-009**: Importing `ceia_aisdk` MUST NOT load the local inference backend; the backend MAY load on `from ceia_aisdk.llm import LLM` or on the first inference call, but MUST NOT load on the top-level package import.
- **FR-010**: `LLM.stream(prompt)` MUST yield an iterator of `str` chunks whose concatenation matches `.chat` under the same fixed seed and temperature, or, if the backend is documented as not bit-stable, MUST yield at least one chunk and nonempty final text.
- **FR-011**: `LLM.session(system=...)` MUST retain history across sends so that a second turn can demonstrate awareness of the first in a short factual fixture.
- **FR-012**: The `LLM` docstring and user documentation MUST state that an instance is not thread-safe, and the implementation MUST NOT introduce a silent global lock to hide that risk.
- **FR-013**: For `llm/small` already resident in memory on CPU, first token of `.chat` or `.stream` MUST appear within 10 seconds.
- **FR-014**: The `[cuda]` extra MUST be installable as `ceia-aisdk[cuda]` from the same published project.
- **FR-015**: With the `[cuda]` extra, a usable NVIDIA GPU, and free memory meeting `llm/small`, `device="auto"` MUST run generation on CUDA and MUST record `cuda` in the operational log.
- **FR-016**: After the `[cuda]` extra is installed, `ceia-aisdk doctor` MUST report whether the CUDA inference binding is present, distinct from whether a GPU is visible.
- **FR-017**: `device="cpu"` MUST force CPU generation even when a GPU and the `[cuda]` extra are present.
- **FR-018**: GPU out-of-memory after generation has started MUST raise `DeviceError` with nonempty remediation that mentions `llm/small` or `device="cpu"`.
- **FR-019**: The 15-minute first-chat KPI MUST be defined as public-index install plus CPU runtime plus `llm/small` pull plus first CPU chat, and MUST NOT include CUDA extra compilation.
- **FR-020**: This feature MUST publish `ceia-aisdk==0.1.0` to the public index as the first public upload of the project.
- **FR-021**: The public project page for `0.1.0` MUST show the 15-minute quickstart and MUST declare Linux x86_64 support without promising Windows.
- **FR-022**: Package classifiers MUST declare Linux support and MUST NOT claim Windows or other architectures.
- **FR-023**: Published wheel and source distribution MUST NOT embed model weight files.
- **FR-024**: Prompts and completions MUST remain on the local machine; this feature MUST NOT send prompt or completion content to a telemetry endpoint.
- **FR-025**: The `[llm]` configuration section MUST support `context_length` with default 8192, used as the generation context window for `LLM` instances that do not override it.
- **FR-026**: Forced-CPU chat MUST be covered by the automated test matrix alongside chat, stream, and a two-turn session.
- **FR-027**: All public failures in this feature MUST derive from `AISDKError` and expose `.remediation` as a nonempty string; device failures MUST use `DeviceError` and obtain failures MUST use `DownloadError` or `ModelNotFoundError` as established by prior features.
- **FR-028**: This feature MUST NOT add a mandatory new CLI subcommand beyond those already provided by the foundations and registry features; the visible increment is the README quickstart plus `doctor` binding status.
- **FR-029**: The documentation increment MUST describe default alias `llm/small`, how to select `medium`, `.chat` / `.stream` / `.session`, `device` values, the `[cuda]` extra, the 15-minute CPU path, non-thread-safety, Linux-only support, and that weights are not in the wheel.
- **FR-030** (P1, may ship in `0.1.0` or first patch): When `device="auto"` and catalog `size_gb` exceeds 90% of observed free GPU memory, the SDK MUST select CPU, emit a `WARNING`, and still return a chat string.
- **FR-031** (P1, may ship in `0.1.0` or first patch): The SDK MUST provide `AsyncLLM` with `.chat`, `.stream`, and session semantics matching `LLM`.
- **FR-032** (P1, may ship in `0.1.0` or first patch): `AsyncLLM` MUST NOT block the event loop on the token hot path beyond what the local inference binding requires; any binding limitation MUST be documented; at least one async smoke test MUST exist when this story ships in the same release as `0.1.0`.
- **FR-033** (P1, MUST NOT block first-chat): The tools API MUST follow the documented OpenAI-ish format (name, JSON schema, call → result).
- **FR-034** (P1, MUST NOT block first-chat): At least one test MUST demonstrate a tool loop with a `get_weather` stub on an alias that declares `tool_use`, using a live capable model or a fixture/recording; if the default alias is unreliable for tools, the test MAY use `llm/medium` marked `capabilities: [tool_use]`.
- **FR-035** (P1, MUST NOT block first-chat): Passing tools to an alias that does not declare `tool_use` MUST raise a clear public error with nonempty remediation.

### Scope Boundaries

Included in this feature:

- Public `LLM` chat, stream, and session on CPU with launch default `llm/small@latest`.
- Obtain of cataloged LLM aliases through the existing registry.
- Optional `[cuda]` extra, GPU generation on a reference NVIDIA machine, and `doctor` distinction between visible GPU and CUDA inference binding.
- First public index publication of `ceia-aisdk==0.1.0`.
- Configuration `[llm] default_alias` and `[llm] context_length`.
- P1 async API, pre-generation memory fallback, and tool use as non-blocking follow-on inside this feature's specification.

Explicitly excluded:

- Fine-tuning.
- Embeddings, retrieval, and RAG (later PRD).
- Vision (later PRD).
- HTTP server and OpenAI-compatible routes (later PRD).
- Multiple inference backends or treating a third-party local server as the runtime.
- Guaranteeing answer quality versus cloud assistants.
- Launch default `medium` for `LLM()`.
- Embedding model weights in the wheel, source distribution, installer, or binary bundle.
- New mandatory CLI commands beyond foundations and registry.
- Catalog signatures, official mirrors, and `LicenseError`.
- Making instances thread-safe.
- Windows, Apple Silicon, ROCm, and Vulkan.
- Counting CUDA compilation time inside the 15-minute first-chat KPI.

### Key Entities

- **LLM Instance**: A non-thread-safe local chat object bound to one resolved alias, one local artifact, and one effective device, exposing `.chat`, `.stream`, and `.session`.
- **Async LLM Instance**: The asyncio-facing counterpart with the same alias, obtain, session, and error semantics (P1).
- **Launch Default Alias**: `llm/small@latest`, overridable by constructor argument or `[llm] default_alias`.
- **Generation Session**: A conversation that retains system text and prior turns so a later send can depend on earlier content.
- **Effective Device**: The device actually used for generation (`cpu`, `cuda`, or `cuda:N`), which may differ from the configured `auto` value after hardware and memory rules.
- **CUDA Extra**: The optional install group that provides a GPU-capable inference binding; its presence is visible to `doctor` separately from GPU detection.
- **Tool Declaration**: A named function with a JSON schema that the model may call; accepted only when the alias lists `tool_use` (P1).
- **Public Release 0.1.0**: The first index publication of the library, CLI, registry, and LLM surface, without embedded weights.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a clean Linux x86_64 CPU machine with a supported Python already installed and working network, 100% of measured first-chat runs starting from a public-index install of `ceia-aisdk` return a nonempty string from `LLM().chat("Say only: ok")` in 15 minutes or less, including the `llm/small` obtain. CUDA extra compilation is outside this clock.
- **SC-002**: `ceia-aisdk==0.1.0` is present on the public index; 100% of reviewed project-page and classifier checks show Linux x86_64 support, the 15-minute quickstart, no Windows promise, and no model weights inside the published artifacts.
- **SC-003**: On the reference NVIDIA machine with the `[cuda]` extra and free memory meeting `llm/small`, 100% of `device="auto"` first-chat runs complete on CUDA (operational log contains `cuda`). If free memory is insufficient and the P1 fallback is present, 100% of those runs still return a string after a CPU fallback and a `WARNING`; otherwise they fail with `DeviceError` and nonempty remediation.
- **SC-004**: For `llm/small` already resident in memory on CPU, 95% of `.chat` first tokens and `.stream` first tokens appear within 10 seconds.
- **SC-005**: 100% of automated import checks show that importing `ceia_aisdk` does not load the inference backend; loading occurs only when the LLM surface is imported or first used.
- **SC-006**: 100% of the P0 automated matrix covers chat, stream, a two-turn session with memory, and forced `cpu` device. When `AsyncLLM` ships in the same release, at least one async test covers the same smoke behavior.
- **SC-007**: When offline mode is on and the alias is uncached, 100% of `LLM` first-use attempts fail within 1 second with `DownloadError` and no hang.
- **SC-008**: 100% of public errors exercised in this feature provide nonempty remediation, and 100% of prompt/completion paths send zero content telemetry.
- **SC-009**: In an evaluation with at least five representative developers on Linux x86_64, at least 90% can install from the public index (or a release-candidate equivalent) and obtain a first nonempty chat reply on the first attempt by following the project-page quickstart, without reading source code.
- **SC-010**: 100% of documentation and docstring reviews for `LLM` state that instances are not thread-safe.

## Assumptions

- PRD-00 and PRD-01 are available: installable package identity, `AISDKConfig`, `DeviceError` / `DownloadError` / `ModelNotFoundError`, `ceia-aisdk doctor`, and `ensure_local` / cataloged `llm/small|medium|large`.
- Linux x86_64 remains the only supported platform; Ubuntu 22.04 or later is the reference environment. Python 3.11–3.13 is already installed for the 15-minute measurement.
- Launch default is `llm/small@latest` by product decision on 2026-09-01; `medium` remains cataloged and selectable. Reverting the default to `medium` requires updating this specification and the 15-minute KPI together.
- Catalog `size_gb` values from the registry are the input to the P1 90% free-memory fallback; this feature is the first to use `size_gb` for device choice.
- Automated CI MUST NOT download production multi-gigabyte weights. Chat/stream/session tests use a tiny local catalog fixture; quality of the curated aliases is a manual checklist on the reference machine.
- Stream versus chat equality is asserted under a fixed seed and temperature when the backend is stable enough; otherwise the documented nonempty-chunk fallback applies.
- The smoke assertion is nonempty text (and may check a short substring or pattern such as `ok`) with a small maximum token budget in tests.
- Informal CPU versus CUDA tokens-per-second numbers may appear in `doctor` or debug logs; they are not a release gate.
- If the team cannot publish a prebuilt `[cuda]` extra artifact, install-from-source documentation of at most 20 lines is the accepted mitigation; CUDA remains a quality gate on the reference machine, not part of the CPU 15-minute KPI.
- `AsyncLLM` and VRAM fallback may land in `0.1.0` if they are ready; if not, they ship in the first patch without retracting the public CPU first-chat claim.
- Tool use does not block `0.1.0`. A skip or deferred test is acceptable for CI when the fixture is a stub, as long as the skip is explicit.
- No new CLI subcommand is required; README quickstart is the primary teaching surface.
- The local inference backend is an implementation choice made in planning; this specification requires local on-device generation and a CUDA extra, not a particular backend name in user documentation beyond what operators need to install the extra.
- The decisions ratified in the PRD program on 2026-09-01 and PRD-02 are the normative sources for this specification.
- The ratified project constitution, version 1.0.0, governs this feature and all downstream SpecKit artifacts.

### Dependencies

- This feature depends on `001-sdk-foundations`: package identity, `AISDKConfig`, device detection, `DeviceError`, logging namespace, `doctor`, and lazy top-level import.
- This feature depends on `002-model-registry`: versioned aliases, `ensure_local`, public metadata including `size_gb` and `capabilities`, offline `DownloadError`, and cataloged `llm/small|medium|large`.
- Later vision, RAG, and server features depend on this `LLM` / `AsyncLLM` contract and on `0.1.0` existing on the public index.
- Production first-chat uses the published `ceia-aisdk` artifacts and the cataloged small alias. Automated tests MUST still serve tiny fixtures locally.
- Changing the launch default from `small` to `medium` is out of scope until a later bandwidth-based KPI review.
