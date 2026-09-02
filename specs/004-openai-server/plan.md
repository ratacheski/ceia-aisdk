# Implementation Plan: OpenAI-Compatible Local Server

**Branch**: `004-openai-server` (feature identifier; Git worktree is currently on `main`) |
**Date**: 2026-09-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-openai-server/spec.md`

## Summary

Add `ceia-aisdk serve` and the `[server]` extra so a developer can point any OpenAI-compatible
client at `http://127.0.0.1:11434/v1`. The increment uses FastAPI and uvicorn (extra-only),
exposes `GET /v1/models` (opaque LLM aliases) and `POST /v1/chat/completions` with and without
SSE, including OpenAI `tools` / `tool_calls` on that same route. It completes the library
one-step completion that PRD-02 left unfinished (`LLM.chat` stays `str`), maps that result onto
the HTTP contract, serializes non-thread-safe instances through a pool with a waiter queue of 8
(HTTP 429 when full), defaults to loopback plus optional Bearer token and localhost CORS, and
publishes **`ceia-aisdk==0.2.0`**. The server never executes tools. P1 adaptive embeddings,
audio, and vision parts return stable refusals and must not wait for voice, vision, or RAG.

## Technical Context

**Language/Version**: Python 3.11, 3.12, and 3.13

**Primary Dependencies**: Existing Typer, Rich, `httpx`, PyYAML, `llama-cpp-python`; FastAPI and
uvicorn in the `[server]` extra only; official `openai` client as a **dev** test dependency

**Storage**: Existing model cache via `ensure_local`; in-memory LLM pool only; no conversation
database; no weights in wheel or sdist; no TLS certificates in-process

**Testing**: pytest unit (fake LLM including tool-call results, pool/queue, auth, CORS, error
mapping); contract (CLI help, import budget, extras, packaging, README, public completion
types); integration (ASGI TestClient / httpx, tiny GGUF fixture, optional OpenAI client against
in-process ASGI, tool-call JSON shape); bind-conflict and live-port tests opt into loopback
sockets; live tool loop on a cataloged `tool_use` alias is a reference-machine checklist; Ruff,
pydoclint, codespell, check-wheel-contents, Twine; pytest-socket default-off

**Target Platform**: Linux x86_64, Ubuntu 22.04+ reference, GitHub Actions Ubuntu x86_64 for
Python 3.11–3.13. CUDA is unchanged from PRD-02 (reference machine, not a required CI job).

**Project Type**: Single Python library with a console-script CLI and an optional local HTTP
server extra

**Performance Goals**: `GET /v1/models` within 2 s after ready (catalog list only, no model
load); happy-path chat and stream match shipped `LLM` equivalence; missing-extra and bind
failures fail fast; queue overflow is immediate 429 (no unbounded wait)

**Constraints**: Default bind `127.0.0.1:11434`, never `0.0.0.0` unless `--host` is explicit;
`import ceia_aisdk` must not load FastAPI, uvicorn, or `llama_cpp`; `serve --help` works without
the extra; message bodies logged only with `--debug`; one in-use `LLM` per alias, never concurrent
generation on that instance; max 8 waiters then 429; no native TLS, no UI, no app launcher; P0
must not wait for voice, vision, or RAG; `/v1/models` must not claim tools on aliases without
`tool_use`; `LLM.chat` remains `str`; serve does not execute tool handlers

**Scale/Scope**: One public subpackage (`server`), one CLI command (`serve`), two P0 HTTP
routes including tools on chat, library completion types on `ceia_aisdk.llm`, reserved P1
routes with 501/400, one extra, next public version `0.2.0`. CI uses the existing tiny GGUF
fixture plus a fake/recording for tool-call shape; production tool quality is a manual
checklist on a cataloged `tool_use` alias.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

### Pre-Research Gate

- **I. PyPI-Ready Library — PASS**: Same distribution name, next minor `0.2.0`. Weights remain
  runtime cache only. `[server]` is an extra, not a second package. Wheel and sdist stay valid
  `uv build` artifacts.
- **II. SpecKit-First Development — PASS**: `spec.md` exists, has no unresolved clarification
  markers, and this plan precedes tasks and implementation.
- **III. Test-First Development — PASS**: Research and contracts define failing tests for extra
  install, CLI help, bind defaults, models list, chat, SSE, tool calls, 401, CORS, 429, bind
  conflict, adaptive refusals, import budget, and packaging before production code. Tasks must
  preserve red-green-refactor ordering.
- **IV. English-Only Repository — PASS**: Specification, plan, research, data model, contracts,
  quickstart, source, docstrings, CLI help, HTTP error bodies, README, and tests are required
  to be in English.
- **V. Complete Public Interface Documentation — PASS**: `serve` help, `ServerError`,
  `create_app`, `LLM.complete`, `ToolCall`, `CompletionResult`, HTTP routes, and README
  serving section require English docstrings or help with parameters, returns/exits,
  exceptions, side effects, and executable examples.
- **Packaging and Tooling — PASS**: FastAPI and uvicorn are added with `uv` to the `[server]`
  extra; `uv.lock` is committed; builds remain `uv build`; publication uses `uv publish`.
  End-user README examples may use `pip install "ceia-aisdk[server]"`.
- **Quality Gates — PASS**: Existing CI gates remain. Server tests that need the extra run under
  `uv sync --all-extras`. Real generation uses the pre-fetched tiny GGUF. Live bind tests are
  loopback-only.

No constitutional violation requires an exception.

### Post-Design Gate

- Phase 1 contracts stay inside the specification: loopback default, opaque aliases, chat
  matching `LLM` text, OpenAI tools on the same route, library one-step tool calls without
  breaking `LLM.chat`, queue 8 → 429, optional Bearer, localhost CORS, `0.2.0` plus `[server]`,
  adaptive refusals that do not wait for PRDs 03–05.
- `AISDKConfig` keeps its four public fields. Serve flags are CLI process options, not new
  config fields.
- FastAPI and uvicorn stay out of `import ceia_aisdk` and out of main dependencies.
- Public HTTP bodies never include Hugging Face names, catalog URLs, prompt dumps at default
  log level, or Python tracebacks.
- Contributor commands in the quickstart use `uv`. User-facing install on the project page uses
  `pip`.
- TDD evidence remains an implementation gate to be encoded by `/speckit-tasks`.

**Result**: PASS. The design is ready for task generation.

## Project Structure

### Documentation (this feature)

```text
specs/004-openai-server/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/
│   └── requirements.md
├── contracts/
│   ├── python-api.md
│   ├── cli.md
│   ├── http-api.md
│   ├── tools.md
│   ├── diagnostics.md
│   └── packaging.md
└── tasks.md                 # Created by /speckit-tasks, not by this command
```

### Source Code (repository root)

```text
.
├── pyproject.toml           # version 0.2.0 at publish; [project.optional-dependencies] server
├── uv.lock
├── README.md                # serve quickstart, bind, token, CORS, queue, tools, reverse-proxy TLS
├── src/ceia_aisdk/
│   ├── __init__.py          # still must not import server, fastapi, uvicorn, llm, llama_cpp
│   ├── errors.py            # add ServerError
│   ├── cli.py               # add serve command; lazy-import server stack
│   ├── _diagnostics.py      # optional_groups includes declared extras (cuda, server)
│   ├── llm/                 # existing; add complete() + ToolCall / CompletionResult
│   └── server/
│       ├── __init__.py      # public create_app; must not run on import ceia_aisdk
│       ├── app.py           # FastAPI factory, CORS, exception handlers, auth
│       ├── openai_compat.py # /v1/models and /v1/chat/completions (incl. tools)
│       ├── adaptive.py      # reserved embeddings/audio routes; vision gate
│       ├── pool.py          # per-alias LLM pool + waiter queue of 8
│       └── messages.py      # OpenAI messages/tools → library complete(); vision detect
└── tests/
    ├── contract/
    │   ├── test_serve_cli_help.py
    │   ├── test_server_import_budget.py
    │   └── test_server_packaging.py
    ├── integration/
    │   ├── test_serve_models_chat.py
    │   ├── test_serve_stream.py
    │   ├── test_serve_tools.py
    │   ├── test_serve_auth_cors.py
    │   ├── test_serve_queue.py
    │   ├── test_serve_bind.py
    │   ├── test_serve_adaptive.py
    │   └── test_serve_openai_client.py
    └── unit/
        ├── test_llm_tool_calls.py
        ├── test_server_pool.py
        ├── test_server_messages.py
        ├── test_server_errors.py
        └── test_server_missing_extra.py
```

**Structure Decision**: Keep the single `src`-layout package. Server internals are a subpackage
so `import ceia_aisdk` stays unchanged. FastAPI is imported only from `ceia_aisdk.server` and
from the `serve` command body. The CLI command itself stays in `cli.py` so it is always
discoverable. Library tool-call types live in `ceia_aisdk.llm` so Python callers and the server
share one contract. Tests stay split so unit tests remain socket-free and FastAPI-optional
where the missing-extra path is proven, while integration tests opt into the extra and the tiny
GGUF.

## Complexity Tracking

No constitutional violations or additional architectural layers require justification.
