# Research: Local LLM Module and First Public Release

**Feature**: `003-llm-module`
**Date**: 2026-09-02

## 1. Inference Backend

**Decision**: Use `llama-cpp-python` as the only local runtime. Load GGUF files returned by
`ensure_local`. Instantiate the binding with `n_ctx` equal to
`min(LLMSettings.context_length, PublicModelMetadata.context_length)`, `n_gpu_layers=0` on CPU
and `n_gpu_layers=-1` on CUDA, and rely on the GGUF embedded chat template rather than a public
`chat_format` argument.

**Rationale**: PRD-02 names this backend. A single runtime keeps the first public release
reviewable. Cataloged v1 aliases are GGUF. Embedded templates match Qwen instruct artifacts
without exposing upstream template names.

**Alternatives considered**:

- vLLM or a local HTTP server as the runtime: excluded by the specification.
- Requiring a public `chat_format` parameter: leaks template choice and is unnecessary when the
  file already contains a template.
- Always using catalog `context_length` (32768 for v1): can over-allocate RAM on first chat;
  the `[llm] context_length` default of 8192 is the launch window.

**Risks and validation**:

- Tiny CI GGUFs may lack a chat template. Integration smoke tests assert a nonempty string, not
  template fidelity. Session coreference on production `llm/small` is a manual checklist item.
- Backend exceptions during load or generation are wrapped in public SDK errors; native traces
  stay out of `str(error)`.

## 2. Import Budget and Module Layout

**Decision**: Keep `ceia_aisdk/llm/` as a public subpackage that is **not** imported from
`ceia_aisdk.__init__`. `from ceia_aisdk.llm import LLM` must not import `llama_cpp`. The binding
is imported inside the first constructor path after `ensure_local` returns. `import ceia_aisdk`
must still exclude `llama_cpp`, `httpx`, `yaml`, Typer, and Rich from `sys.modules`.

Layout:

```text
ceia_aisdk/llm/__init__.py      # export LLM, AsyncLLM, Session, errors used here
ceia_aisdk/llm/model.py         # class LLM
ceia_aisdk/llm/async_model.py   # class AsyncLLM
ceia_aisdk/llm/session.py       # sync session
ceia_aisdk/llm/settings.py      # [llm] table loader
ceia_aisdk/llm/backend.py       # lazy llama_cpp adapter (private)
ceia_aisdk/llm/devices.py       # effective-device + VRAM margin (private)
```

**Rationale**: The specification allows loading on LLM import or first call; delaying until
construction after `ensure_local` preserves a cheap `from ceia_aisdk.llm import LLM` and avoids
initializing CUDA at import time.

**Alternatives considered**:

- Importing `llama_cpp` in `llm/__init__.py`: fails the “MAY load on import LLM” option in the
  most expensive way and would make merely importing the type pull CUDA libraries.
- Re-exporting `LLM` from the package root: would force every `import ceia_aisdk` to see the
  submodule graph; rejected.

**Risks and validation**:

- Extend `_FORBIDDEN_ROOT_IMPORTS` checks: `import ceia_aisdk` still forbids `llama_cpp`.
- A second check: `from ceia_aisdk.llm import LLM` still forbids `llama_cpp` in `sys.modules`.

## 3. LLM Settings Versus `AISDKConfig`

**Decision**: Do not add `default_alias` or `context_length` to the public `AISDKConfig` field
set. Load a sibling immutable `LLMSettings` from the same `~/.ceia-aisdk/config.toml` `[llm]`
table, with the same precedence pattern: explicit constructor arguments, `CEIA_AISDK_LLM_*`
environment variables, TOML `[llm]`, defaults.

Defaults: `default_alias = "llm/small@latest"`, `context_length = 8192`.

`LLM("medium")` and `LLM("llm/medium")` pass through the constructor and win over TOML.
Unqualified sizes supply `domain="llm"` to `resolve` / `ensure_local`.

`LLM(..., device=)` overrides `AISDKConfig.device` for that instance only.

**Rationale**: Foundations froze four core fields. PRD-02 adds an `[llm]` table, not a breaking
change to `AISDKConfig`. Environment keys keep the layered model consistent for CI.

**Alternatives considered**:

- Extending `AISDKConfig` with optional LLM fields: breaks the 001 field set and every existing
  config test.
- TOML-only with no environment keys: harder to pin in CI without writing a home file.

## 4. Device Selection, CUDA Extra, and VRAM Fallback

**Decision**: Resolve the configured device with existing `get_device` / `select_device`. Then
apply this feature’s rules:

- `device="cpu"` → CPU, `n_gpu_layers=0`, even if a GPU and the extra are present.
- `device="auto"` plus a usable GPU plus CUDA binding present → CUDA, `n_gpu_layers=-1`, and an
  operational log line that contains the token `cuda`.
- `device="auto"` plus GPU visible but no CUDA binding → CPU (do not raise). Log at `WARNING`
  that the extra is missing or the binding is CPU-only.
- `device="cuda"` / `cuda:N` plus missing binding or missing GPU → `DeviceError` with
  remediation mentioning `llm/small` or `device="cpu"`.
- P1 pre-generation fallback (ships in this 0.1.0 design): if `device="auto"` and
  `size_gb > 0.9 * (free_vram_mib / 1024)`, choose CPU, log `WARNING`, and continue. Explicit
  CUDA never silent-falls-back.
- After generation has started, wrap backend out-of-memory as `DeviceError` with the same
  remediation class.

`[cuda]` extra: `llama-cpp-python` CPU wheels remain a **main** dependency so
`pip install ceia-aisdk` meets the 15-minute CPU KPI without compiling. The extra cannot place a
CUDA wheel on public PyPI by itself. Document a ≤ 20 line install path:

1. `pip install ceia-aisdk[cuda]` (records the extra; may reinstall the same distribution name);
2. rebuild or install a CUDA-capable `llama-cpp-python` using `CMAKE_ARGS="-DGGML_CUDA=on"` or
   the project’s documented extra index for prebuilt CUDA wheels, if the team publishes one.

Doctor reports two independent facts: GPU visible (existing probe) and CUDA inference binding
present (`yes` / `no`) by importing `llama_cpp` **only in the CLI diagnostic process** and
inspecting GPU-offload support, without constructing a model.

**Rationale**: CUDA compilation is the top onboarding failure. The specification already splits
the 15-minute CPU clock from the CUDA quality gate. Amending the 001 “doctor must not import
inference backends” rule is required by FR-016 and is scoped to the CLI, not `import ceia_aisdk`.

**Alternatives considered**:

- Making CUDA wheels a hard pip extra from PyPI: not actually hosted for this backend.
- Silent global lock around the instance: forbidden by the specification.
- Applying the 90% margin to explicit `device="cuda"`: would violate User Story 5.

## 5. Chat, Stream, Session, and Thread Safety

**Decision**: `LLM.chat(prompt, *, max_tokens=512, temperature=0.8, seed=None)` is one-shot and
does not retain history on the instance. `LLM.stream` yields `str` chunks from the same
completion path. `LLM.session(system=None)` returns a `Session` whose `.send` / `.stream` append
user/assistant turns.

Tests that compare stream concatenation to chat pass `temperature=0` and a fixed `seed`. If the
binding is not bit-stable under those knobs, document it and assert ≥ 1 chunk plus nonempty
final text.

Instances are not thread-safe. Docstrings and README state that. Do not add a process-wide lock.

First-token ≤ 10 s is a warm-resident measurement on `llm/small` CPU, recorded as a performance
test that may be marked for the reference machine when CI only has a tiny GGUF.

Progress: `ensure_local` already accepts `progress: Callable[[int, int | None], None]`. `LLM`
passes a Rich callback when stderr is a TTY; otherwise a single English line or silence.

**Rationale**: Matches PRD-02 surfaces without inventing a stateful `chat` that surprises users.
Reuse of the registry progress hook avoids a second downloader.

**Alternatives considered**:

- Keeping history on `LLM` itself: conflicts with one-shot `.chat` semantics.
- Progress inside every `ensure_local` by default: already rejected in PRD-01 for libraries.

## 6. AsyncLLM

**Decision**: Ship `AsyncLLM` in the same 0.1.0 design. Mirror constructors and methods. Because
`llama-cpp-python` generation is blocking, run the token hot path in `asyncio.to_thread` (or an
equivalent executor). Document that limitation. `AsyncLLM.stream` is an async iterator.
Include at least one asyncio smoke test with a timeout.

**Rationale**: The specification allows 0.1.0 or the first patch; the wrapper is small once
`LLM` exists. Documented executor offload satisfies “do not block beyond what the binding
requires.”

**Alternatives considered**:

- Deferring AsyncLLM entirely: increases the chance of a mismatched async contract later.
- Native async inside llama.cpp: not offered by the binding.

## 7. Tool Use

**Decision**: Design the public tools contract in this feature. Sequence implementation last.
It MUST NOT block first-chat or the `0.1.0` upload.

Public shape (OpenAI-ish): a sequence of tools with `name`, JSON `parameters` schema, and an
optional Python callable. Chat/session may run a bounded call → result loop. Passing tools to an
alias whose `capabilities` lack `tool_use` raises `CapabilityError`. CI may use a fixture or
explicit skip if the tiny GGUF cannot call tools; production `llm/small@1` already declares
`tool_use`.

**Rationale**: PRD-02 is explicit that tools are P1 and non-blocking. Designing the types now
prevents the server feature from inventing a second convention.

**Alternatives considered**:

- Omitting types until PRD-06: would freeze an incomplete 0.1.0 public surface or force a
  later break.

## 8. Testing Strategy and Fixtures

**Decision**: Split tests:

- **Unit**: fake backend protocol covering alias default, settings precedence, session history,
  device/VRAM rules, capability rejection, error wrapping. No `llama_cpp`, no sockets.
- **Contract**: import budget, public signatures, docstrings, doctor copy-block keys, wheel
  contents (no `.gguf` / weight payloads), Linux classifiers, README quickstart phrases.
- **Integration**: real `llama_cpp` plus a tiny GGUF served like PRD-01 (loopback catalog via
  `CEIA_AISDK_CATALOG`). Assert nonempty chat, ≥ 1 stream chunk, forced CPU, offline miss ≤ 1 s.
  Session coreference on the tiny model is best-effort; if it fails, keep the test on the fake
  backend and record a manual checklist for `llm/small`.
- **Performance**: warm first-token 10 s is a reference-machine / opt-in test, not a default CI
  gate on the tiny model.
- **Packaging**: `uv build`, check-wheel-contents, Twine, isolated install smoke that imports
  `LLM` without loading `llama_cpp` until construction.

Do not commit multi-gigabyte weights. Provide `scripts/fetch-llm-test-fixture.sh` to place a
tiny GGUF (llama.cpp `stories15M` class, typically ~11 MiB) under `tests/fixtures/` (gitignored).
CI downloads it before pytest. If the file is missing, real-backend tests skip with an explicit
reason; fake-backend tests still run.

**Rationale**: Matches the PRD mitigation: CI smoke plus manual quality on the curated alias.

**Alternatives considered**:

- Committing an 11 MiB GGUF: simpler locally, but binaries in git are optional and not required
  if CI fetches a pinned URL and checksum.
- Hitting Hugging Face production `llm/small` in CI: rejected (2.3 GiB, flaky, slow).

## 9. Diagnostics Amendment

**Decision**: Extend `ceia-aisdk doctor` (no new subcommand):

- `optional_groups` reports `cuda` as an installable extra, not `cuda:reserved`.
- New copy-block field `cuda_binding=<yes|no>`.
- Binding probe: `importlib.util.find_spec("llama_cpp")` then a bounded import that reads
  GPU-offload support. Missing module → `no`. Failed import → `no` plus a non-failing INFO
  check (foundation remains usable on CPU).
- Doctor still makes zero network calls, does not download models, and stays within 5 seconds
  on CPU-only reference hardware.
- `import ceia_aisdk` still must not import `llama_cpp`.

**Rationale**: FR-016 and the CUDA onboarding risk require distinguishing “GPU visible” from
“binding cannot offload.”

**Alternatives considered**:

- A new `ceia-aisdk llm` command: forbidden as a mandatory subcommand.
- Leaving doctor unchanged: would fail the CUDA extra acceptance scenario.

## 10. Publication of `0.1.0`

**Decision**: This feature is the first `uv publish` to public PyPI of `ceia-aisdk==0.1.0`.
Keep `0.1.0.dev0` during development; the release task sets `project.version` to `0.1.0`.
README becomes the PyPI long description: 15-minute CPU quickstart, Linux x86_64 only, no
Windows promise, `[cuda]` extra instructions, weights not in the wheel, default `llm/small`.
Classifiers already declare POSIX/Linux. Wheel/sdist must not contain GGUF or other weight
files. TestPyPI rehearsal is allowed and does not count as the public release.

Contributor commands stay on `uv`. End-user install examples on the project page use
`pip install ceia-aisdk` as the supported user contract.

**Rationale**: Constitution I and the program index make 0.1.0 the first moment the 15-minute
KPI is measurable by a stranger.

**Alternatives considered**:

- Publishing during PRD-00/01: already rejected.
- A separate distribution name for CUDA: rejected; one project, extras only.
