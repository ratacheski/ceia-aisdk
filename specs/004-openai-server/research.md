# Research: OpenAI-Compatible Local Server

**Feature**: `004-openai-server`
**Date**: 2026-09-02

## 1. HTTP Stack and Extra

**Decision**: Declare `[project.optional-dependencies] server = ["fastapi>=0.115", "uvicorn>=0.32"]`.
The extra is the only supported way to obtain the serving stack. Main dependencies stay as in
`0.1.0` (no FastAPI, no uvicorn). The official `openai` package is a **dev** dependency for one
integration test, not part of `[server]`.

`ceia-aisdk serve` is always registered on the Typer app. The command body lazy-imports
`ceia_aisdk.server`. If FastAPI or uvicorn is missing, raise `ServerError` whose remediation is
`pip install "ceia-aisdk[server]"` (and the equivalent `uv` contributor form in docs). Help
(`serve --help`) MUST succeed without the extra.

**Rationale**: PRD-06 names FastAPI and uvicorn and requires the extra to be absent from `0.1.0`.
A always-visible command with a remediation path beats a missing subcommand that users cannot
discover.

**Alternatives considered**:

- Adding FastAPI to main dependencies: bloats the first-chat install and violates FR-024.
- A separate distribution `ceia-aisdk-server`: rejected by the program (one PyPI project).
- Flask or stdlib `http.server`: would not match the PRD extra contract or SSE ergonomics.

## 2. Import Budget and Module Layout

**Decision**: Do not import `ceia_aisdk.server` from `ceia_aisdk.__init__` or from `cli.py` at
module level. Layout:

```text
ceia_aisdk/server/__init__.py      # export create_app
ceia_aisdk/server/app.py           # FastAPI factory
ceia_aisdk/server/openai_compat.py # P0 routes
ceia_aisdk/server/adaptive.py      # P1 reserved routes and chat gates
ceia_aisdk/server/pool.py          # LLM pool + admission queue
ceia_aisdk/server/messages.py      # request translation
```

Extend `_FORBIDDEN_ROOT_IMPORTS` with `fastapi` and `uvicorn`. `from ceia_aisdk.llm import LLM`
remains free of FastAPI. Importing `ceia_aisdk.server` MAY import FastAPI when the extra is
installed; that import is not on the `import ceia_aisdk` path.

**Rationale**: Same isolation pattern as registry and LLM. Help and doctor stay cheap.

**Alternatives considered**:

- Importing FastAPI in `cli.py` at load: would make every CLI invocation require the extra.
- Re-exporting `create_app` from the package root: would pull the extra graph into
  `import ceia_aisdk`.

## 3. Bind, Ready Log, and Port Collision

**Decision**: Defaults `--host 127.0.0.1` and `--port 11434`. Pass them to `uvicorn.run` (or
`uvicorn.Server` with `Config`). After the server reports started, log one INFO line containing
the absolute URL `http://<host>:<port>/v1`. Do not log request bodies.

Catch bind `OSError` / `SystemExit` from uvicorn and raise `ServerError` with remediation:
change `--port` or stop the occupant (name a local serving product on 11434, for example
Ollama). Fail fast; do not retry other ports.

Explicit `--host 0.0.0.0` is allowed. Help and README MUST warn that this exposes the process
beyond the machine. The default MUST remain loopback. Documented default is IPv4 `127.0.0.1`,
not IPv6 `::1`.

**Rationale**: Port 11434 is an intentional drop-in. Coexistence on the same port is not a
requirement; a clear bind error is.

**Alternatives considered**:

- Auto-increment port: would surprise clients configured for 11434.
- Binding `::1` by default: diverges from the specified address.

## 4. Models List

**Decision**: `GET /v1/models` reads the active catalog (bundled or `CEIA_AISDK_CATALOG`) and
returns OpenAI `{object: "list", data: [...]}` where each `id` is an opaque `domain/size` alias
in the `llm` domain (`llm/small`, `llm/medium`, `llm/large`, plus any other cataloged LLM
sizes). Do not include Hugging Face names, URLs, or SHA-256. Do not claim tool calling on an
alias that lacks catalog `tool_use`. README and `model info` remain the place that documents
which aliases declare `tool_use`.
`owned_by` is the constant `ceia-aisdk`. Do not construct or load an `LLM`.

Clients MAY still send a versioned alias (`llm/small@2`) in chat; `resolve` already accepts it.
The list surface stays unversioned size aliases so ids match the spec examples.

Add a package-private catalog listing helper used by the server (and tests). A public
`registry.list_aliases` is optional; if added, it must return only opaque aliases and stay
URL-free. Prefer a focused server helper over expanding the registry public surface unless
tests need it independently.

**Rationale**: Listing must finish within 2 s and must not leak origin fields. Loading weights
on `/v1/models` would miss SC-001.

**Alternatives considered**:

- Listing only cached aliases: would hide models the registry can still obtain.
- Putting a non-standard `capabilities` array on every `/v1/models` row: optional later; the
  official client ignores unknown fields but the P0 contract does not require it.

## 5. Chat Completions Mapping

**Decision**: Add a public one-step API on `LLM` (name `complete` unless planning finds a
clearer synonym) that accepts OpenAI-shaped `messages` plus optional tools and returns a
`CompletionResult`: either assistant `content` or `tool_calls`. `LLM.chat` / `.stream` /
`.session` stay unchanged and still return `str` / `Iterator[str]`.

The server holds pooled `LLM` instances and, under the per-alias lock, calls `complete` (and a
streaming counterpart) with the translated request. That is the only way `/v1/chat/completions`
can return `tool_calls` without inventing them.

Translation:

- Require `model` and `messages`. Missing → 400.
- `temperature` default `0.8`, `max_tokens` default `512` (same as `LLM.chat`).
- Optional `seed` is accepted and forwarded so tests can match stream vs non-stream.
- `stream` default `false`.
- `n` other than 1 → 400.
- Each message `role` is `system`, `user`, `assistant`, or `tool`.
- `content` MUST be a string for P0 text. Array content with `image_url` / image parts → 400
  “vision is not available”.
- `tools` / `tool_choice` are accepted when the alias declares `tool_use`. Otherwise
  `CapabilityError` / HTTP 400. Tools are never silently ignored.
- Assistant messages MAY include `tool_calls`. Tool messages MUST include `tool_call_id`.
- Unknown OpenAI fields are ignored unless they change generation semantics that we reject
  (`n`, vision parts).

A single user string message without tools equals `LLM.chat(prompt)` on that alias (same
backend path for the text). Multi-turn `messages` are the history for this request only. The
pool MUST NOT keep a `Session` between HTTP requests. The server MUST NOT run `handler`
callables; those remain an optional library convenience and are out of the HTTP path.

Non-stream response shape (minimum):

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 0,
  "model": "<opaque alias>",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "<text>"},
      "finish_reason": "stop"
    }
  ],
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
}
```

Token counters MAY be zero when the backend does not expose them. The official client accepts
zero usage.

SSE when `stream: true`: `text/event-stream` with at least one `data: {chat.completion.chunk}`
line. Text turns use `choices[0].delta.content`. Tool-call turns use OpenAI-shaped
`delta.tool_calls`. The stream ends with `data: [DONE]`. Concatenated text deltas equal
non-stream content under the LLM equivalence rules (`temperature=0` and fixed `seed` when
bit-stable; otherwise ≥ 1 chunk and nonempty text).

When the result is tool calls, non-stream `choices[0].message.tool_calls` is populated,
`content` MAY be null, and `finish_reason` is `tool_calls`.

**Rationale**: Agents use the same POST for tools; there is no `/v1/tools`. The shipped
`LLM.chat` → `str` cannot express tool calls without a breaking change, so a one-step
`complete` is required in the library first. `Session.send` always generates and cannot replay
history without extra calls.

**Alternatives considered**:

- Flattening history into one user prompt: loses roles and diverges from `LLM.session`.
- Changing `LLM.chat` to return a union type: breaks the `0.1.0` first-chat contract.
- Keeping HTTP tools as 400 until a later minor: rejected after product review; tools are
  part of chat completions and do not wait for voice or vision.
- Running `ToolDeclaration.handler` inside `serve`: the OpenAI client owns execution.

## 6. Pool and Queue

**Decision**: In-memory `ModelPool`:

- Key: canonical alias after `resolve` (`domain/size@N`).
- Value: one `LLM` instance created on first use (`ensure_local` + construct).
- Per-alias `asyncio.Lock` (or equivalent) so generation and construction never overlap on
  that instance.
- Process-wide waiter cap **8**. If the alias lock is busy and there are already 8 waiters,
  return HTTP 429 immediately with stable JSON. A waiter is a request that has entered the
  HTTP handler and cannot yet acquire the alias lock.
- In-flight generations do not count against the 8. Different aliases may run at most one
  generation each (two aliases → two in-flight, still one lock per instance).
- Blocking `LLM` work runs in `asyncio.to_thread` while the alias lock is held.
- No disk writes of messages. Shutdown drops the pool; no conversation files.

**Rationale**: Matches FR-020/FR-021 and the non-thread-safe `LLM` docstring. A global waiter
cap bounds memory regardless of alias count.

**Alternatives considered**:

- Per-alias queue of 8 (up to 8×N waiters): weaker memory bound.
- Process-wide lock of 1: over-serializes independent aliases.
- Creating a new `LLM` per request: safe but reloads weights; rejected for the default pool.
- Waiting with a timeout instead of 429: rejected by the spec.

## 7. Auth, CORS, and Logging

**Decision**:

- `--token` optional. When unset, no auth. When set, every `/v1/*` request (including
  `GET /v1/models` and reserved P1 routes) requires `Authorization: Bearer <token>` compared
  with `hmac.compare_digest`. Missing, wrong, or non-Bearer → 401. Constant-time compare on
  equal-length secrets; treat length mismatch as 401 without leaking.
- Default CORS: allow only localhost origins — `http://localhost`, `http://127.0.0.1`, and
  those hosts with an explicit port. Disallow other origins. Handle OPTIONS preflight.
- `--cors`: boolean flag; relaxes to allow any origin (`allow_origins=["*"]`) without
  credentials. Document that this is for local browser tools, not a multi-user policy.
- `--debug`: sets log level DEBUG and is the only flag that MAY log `messages` bodies. Default
  process log level remains `AISDKConfig.log_level` (WARNING unless configured). INFO ready
  logs must not include message contents.

**Rationale**: Spec locks optional Bearer, localhost CORS, and “debug flag” for bodies.

**Alternatives considered**:

- Config.toml token: not requested; keep secrets on the CLI for this slice.
- Origin allow-list flag: extra surface; boolean `--cors` matches the spec.

## 8. HTTP Errors and Adaptive Routes

**Decision**: Stable OpenAI-shaped error body, never a traceback:

```json
{
  "error": {
    "message": "<English explanation>",
    "type": "<machine type>",
    "code": "<machine code>",
    "remediation": "<nonempty next action>"
  }
}
```

Mapping:

| Condition | Status | Notes |
|-----------|--------|--------|
| Missing extra / CLI bind failure | N/A (CLI) | `ServerError`, exit 1, stderr message + remediation |
| Missing/wrong Bearer when `--token` set | 401 | `code=invalid_api_key` |
| Validation, vision parts | 400 | vision message as specified |
| `tools` on alias without `tool_use` | 400 | `CapabilityError` mapped |
| Unknown alias | 404 | `ModelNotFoundError` mapped |
| Occupied queue | 429 | remediation mentions retry / fewer parallel requests |
| Offline cache miss / obtain failure | 503 | `DownloadError` |
| Device failure | 503 | `DeviceError` |
| Generation / overflow | 400 | `GenerationError` |
| Reserved module routes without module | 501 | `/v1/embeddings`, `/v1/audio/transcriptions`, `/v1/audio/speech` |
| Assistants, batches, files, fine-tune, unknown | 404 | FastAPI default not-found, same JSON envelope |
| Unhandled exception | 500 | stable JSON, no traceback, generic remediation |

P1 probes (`importlib.util.find_spec` for future `ceia_aisdk.rag`, `ceia_aisdk.voice`,
`ceia_aisdk.vision`) MAY succeed later without changing P0 routes. For `0.2.0` those modules
are absent; tests assert 501/400 for embeddings, audio, and vision parts. Tool calls are P0
on `/v1/chat/completions` via the library `complete` path.

**Rationale**: Spec allows 404 or 501 for missing modules. 501 on **reserved** URLs is
testable and distinct from unknown OpenAI product URLs.

**Alternatives considered**:

- Returning 404 for embeddings: harder to tell “typo” from “not shipped”.
- Implementing embeddings against a stub: would fake a module the program has not shipped.
- Leaving tools on 400: rejected; tools belong on chat completions.

## 9. Testing Strategy

**Decision**:

- **Unit**: admission queue (8 waiters → reject), message translation, vision detection,
  library `complete` tool-call vs text results, error envelope, missing-extra import path
  without FastAPI.
- **Contract**: `[server]` extra declared; `serve` on root help; serve help flags and examples;
  `server` not imported from package root; wheel has no weights; README phrases; doctor
  `optional_groups` includes `server`.
- **Integration**: FastAPI/Starlette `TestClient` or `httpx.ASGITransport` (in-process, no
  pytest-socket conflict) for models, chat, SSE, tool-call JSON / `role: tool` follow-up, 401,
  CORS, 429, adaptive 501/400. Tiny GGUF + loopback catalog for nonempty text generation. Tool
  shape uses a fake backend or recording when the tiny GGUF cannot call tools. One test drives
  `openai.OpenAI` through an httpx client bound to the ASGI app (or a loopback live server if
  the client cannot take a transport).
- **Bind conflict**: enable loopback sockets, occupy the port, run `serve`, expect `ServerError`.
- **Help examples**: extend the executable-example harvester to skip long-running `serve`
  without `--help`, so a documented `ceia-aisdk serve` example does not hang CI.

Do not download production weights. Reuse `scripts/fetch-llm-test-fixture.sh`.

**Rationale**: ASGI in-process tests cover the OpenAI contract without opening 11434 in every
test. Bind and live-port cases are explicit exceptions.

**Alternatives considered**:

- Always spawning uvicorn on 11434: flaky under parallel pytest and collides with Ollama on
  developer machines.
- Making `openai` a runtime extra dependency: unnecessary for serving.

## 10. Diagnostics and CLI Help

**Decision**: `optional_groups` lists extras **declared** by the installed distribution
(`Provides-Extra`), currently `cuda` and after this feature `cuda,server` (stable order).
Continue to report declared extras even if the extra is not installed in the environment, matching
the CUDA contract. `doctor` still must not import FastAPI or start a server.

Root help lists `serve` with nonempty short help and an example that includes `serve --help`
and/or `serve`. Serve help documents `--host`, `--port`, `--token`, `--cors`, `--debug`,
defaults, loopback warning, extra requirement, and at least one executable example.

**Rationale**: FR-027. Reading metadata avoids a third hardcoded tuple drift.

**Alternatives considered**:

- Hardcoding `_OPTIONAL_GROUPS = ("cuda", "server")`: works but drifts when `[apps]` arrives.

## 11. Publication of `0.2.0`

**Decision**: This feature is the next `uv publish` of the same project. Development MAY use
`0.2.0.dev0`; the release task sets `project.version` to `0.2.0`. README gains a serving
section: `pip install "ceia-aisdk[server]"`, `ceia-aisdk serve`, `base_url`
`http://127.0.0.1:11434/v1`, opaque aliases, token, CORS, queue 8 / 429, port conflict,
reverse-proxy TLS, Linux x86_64, and that voice, vision, RAG, and the app launcher are out of
this slice. Wheel/sdist still contain no weights. TestPyPI does not count as the public release.

**Rationale**: Program table: library + serve is the second public demo. User instruction locks
the version to `0.2.0` because this ships against `0.1.0` without waiting for PRDs 03–05.

**Alternatives considered**:

- Waiting for voice/vision/RAG to bump the minor: rejected by the feature description.
- Publishing `[server]` as `0.1.1`: the program uses minors per merged PRD increment.
