# Implementation Plan: Local LLM Module and First Public Release

**Branch**: `003-llm-module` (feature identifier; Git worktree is currently on `main`) |
**Date**: 2026-09-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-llm-module/spec.md`

## Summary

Add the public `ceia_aisdk.llm` surface so a developer can `pip install ceia-aisdk` from the
public index, construct `LLM()`, and receive a local chat string from `llm/small@latest`. The
increment uses `llama-cpp-python` (CPU wheel as a main dependency, CUDA via the `[cuda]` extra
and documented rebuild or prebuilt index), registry `ensure_local`, `[llm]` settings beside
`AISDKConfig`, `doctor` CUDA-binding detection, and the first upload of `ceia-aisdk==0.1.0`.
P1 `AsyncLLM` and pre-generation VRAM fallback are designed into the same release. Tool use is
specified last and must not block first-chat.

## Technical Context

**Language/Version**: Python 3.11, 3.12, and 3.13

**Primary Dependencies**: Existing Typer, Rich, `httpx`, and PyYAML; `llama-cpp-python` as the
local GGUF runtime (lazy-imported); standard library `asyncio` for `AsyncLLM` executor offload

**Storage**: Existing model cache via `ensure_local`; optional `[llm]` keys in
`~/.ceia-aisdk/config.toml`; no database; no weights in wheel or sdist

**Testing**: pytest unit (fake backend), contract (import budget, doctor, packaging),
integration (tiny GGUF + loopback catalog), optional reference-machine performance; Ruff,
pydoclint, codespell, check-wheel-contents, Twine; pytest-socket default-off; CUDA quality gate
is manual on the reference NVIDIA machine

**Target Platform**: Linux x86_64, Ubuntu 22.04+ reference, GitHub Actions Ubuntu x86_64 for
Python 3.11–3.13 (CPU). CUDA is not a required CI matrix job.

**Project Type**: Single Python library with a console-script CLI

**Performance Goals**: 15-minute CPU first-chat from public-index install including `llm/small`
pull; warm `llm/small` first token at or below 10 s on CPU (reference machine); foundation p95
import at or below 200 ms without loading `llama_cpp`; offline LLM cache-miss failure at or
below 1 s

**Constraints**: Launch default `llm/small@latest` not `medium`; instances not thread-safe and
not globally locked; prompts never leave the machine; CUDA compile time excluded from the
15-minute clock; doctor may import `llama_cpp` only in the CLI process; `import ceia_aisdk` and
`from ceia_aisdk.llm import LLM` must not load `llama_cpp`; no new mandatory CLI subcommand;
tool use must not block `0.1.0`

**Scale/Scope**: One public subpackage (`llm`), two public model classes, one session type, one
settings object, `[cuda]` extra documentation, doctor binding field, first PyPI version
`0.1.0`. CI uses a tiny GGUF fixture; production quality is a manual checklist on curated
aliases.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

### Pre-Research Gate

- **I. PyPI-Ready Library — PASS**: This increment is the first public upload. Weights remain
  runtime cache only. Wheel and sdist stay valid `uv build` artifacts. Versioning follows the
  release task (`0.1.0.dev0` until publish).
- **II. SpecKit-First Development — PASS**: `spec.md` exists, has no unresolved clarification
  markers, and this plan precedes tasks and implementation.
- **III. Test-First Development — PASS**: Research and contracts define failing tests for
  defaults, chat/stream/session, import budget, offline miss, forced CPU, doctor binding,
  packaging, and (when present) async, VRAM fallback, and tools before production code. Tasks
  must preserve red-green-refactor ordering.
- **IV. English-Only Repository — PASS**: Specification, plan, research, data model, contracts,
  quickstart, source, docstrings, CLI help, errors, README, and tests are required to be in
  English.
- **V. Complete Public Interface Documentation — PASS**: `LLM`, `AsyncLLM`, `Session`,
  `LLMSettings`, new errors, and updated `doctor` help require English docstrings or help with
  parameters, returns/exits, exceptions, side effects, and executable examples.
- **Packaging and Tooling — PASS**: `llama-cpp-python` is added with `uv`; `uv.lock` is
  committed; builds remain `uv build`; publication uses `uv publish` to PyPI. End-user README
  examples may use `pip install ceia-aisdk`.
- **Quality Gates — PASS**: Existing CI gates remain. Real-backend tests require a pre-fetched
  tiny GGUF. CUDA inference is a reference-machine gate, not a required GitHub Actions job.

No constitutional violation requires an exception. The 001 rule that `doctor` must not import
inference backends is **amended in this feature** for a bounded CLI-only `llama_cpp` capability
probe (see [research.md](research.md) §9). `import ceia_aisdk` is unchanged.

### Post-Design Gate

- Phase 1 contracts stay inside the specification: default `small`, CPU 15-minute path, CUDA
  extra as quality gate, no weights in artifacts, no new mandatory CLI command, no thread-safety
  lock, tools non-blocking.
- `AISDKConfig` keeps its four public fields; `[llm]` is a sibling settings object.
- `llama_cpp` is isolated from `import ceia_aisdk` and from `from ceia_aisdk.llm import LLM`.
- Public types do not expose upstream repository names or catalog URLs.
- All contributor commands in the quickstart use `uv`. User-facing install on the project page
  uses `pip`.
- TDD evidence remains an implementation gate to be encoded by `/speckit-tasks`.

**Result**: PASS. The design is ready for task generation.

## Project Structure

### Documentation (this feature)

```text
specs/003-llm-module/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/
│   └── requirements.md
├── contracts/
│   ├── python-api.md
│   ├── configuration.md
│   ├── diagnostics.md
│   ├── packaging.md
│   └── tools.md
└── tasks.md                 # Created by /speckit-tasks, not by this command
```

### Source Code (repository root)

```text
.
├── pyproject.toml           # add llama-cpp-python; fill [cuda] extra; version 0.1.0 at publish
├── uv.lock
├── README.md                # 15-minute PyPI quickstart
├── scripts/
│   └── fetch-llm-test-fixture.sh
├── src/ceia_aisdk/
│   ├── __init__.py          # still must not import llm or llama_cpp
│   ├── errors.py            # add GenerationError, CapabilityError
│   ├── _diagnostics.py      # cuda_binding field; optional_groups no longer reserved-only
│   └── llm/
│       ├── __init__.py      # LLM, AsyncLLM, Session, LLMSettings
│       ├── settings.py
│       ├── model.py
│       ├── async_model.py
│       ├── session.py
│       ├── backend.py       # private lazy adapter
│       └── devices.py       # private effective device + 0.9 margin
└── tests/
    ├── contract/
    │   ├── test_llm_api.py
    │   ├── test_llm_import_budget.py
    │   └── test_llm_packaging.py
    ├── integration/
    │   ├── test_llm_chat.py
    │   ├── test_llm_stream_session.py
    │   ├── test_llm_offline.py
    │   ├── test_llm_device_cpu.py
    │   └── test_async_llm.py
    ├── performance/
    │   └── test_llm_first_token.py    # reference / opt-in
    └── unit/
        ├── test_llm_settings.py
        ├── test_llm_devices.py
        ├── test_llm_session.py
        └── test_llm_capabilities.py
```

**Structure Decision**: Keep the single `src`-layout package. LLM internals are a subpackage so
the package root import graph stays unchanged. The private `backend.py` adapter is the only
module allowed to import `llama_cpp`. Diagnostics stay in the CLI process. Tests stay separated
so fake-backend units remain socket-free and `llama_cpp`-free while integration tests opt into
a pre-fetched tiny GGUF and loopback catalog.

## Complexity Tracking

No constitutional violations or additional architectural layers require justification. The
doctor binding probe is a scoped amendment of a prior side-effect rule, not a new project.
