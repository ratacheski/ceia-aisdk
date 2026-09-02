# Data Model: OpenAI-Compatible Local Server

**Feature**: `004-openai-server`
**Date**: 2026-09-02

This feature has no database. Persistent state remains the registry model cache. Serving state
is in-memory and dies with the process. Conversation history is never written to disk.

## 1. Serve Settings

### Purpose

Process bind, authentication, CORS, and logging flags for one `ceia-aisdk serve` invocation.

### Fields

- `host: str` — Bind address. Default `127.0.0.1`.
- `port: int` — Bind port. Default `11434`. Range 1–65535.
- `token: str | None` — Optional shared secret. When set, Bearer auth is required.
- `cors_open: bool` — When false (default), only localhost origins. When true (`--cors`), any
  origin.
- `debug: bool` — When true (`--debug`), log level DEBUG and message bodies MAY be logged.

### Validation

- Default `host` is never `0.0.0.0`; explicit host may be.
- Empty `--token` after stripping is treated as unset or rejected with `ServerError`.
- Invalid port raises a CLI usage error (exit 2) or `ServerError`.

### Persistence

None. Flags are not written to `config.toml` in this feature.

## 2. Server Error

### Purpose

Public CLI/process failure for missing extra and bind conflicts.

### Representation

`ServerError(AISDKError)` with nonempty `message` and `remediation`.

### Typical cases

- FastAPI/uvicorn missing → remediation names `ceia-aisdk[server]`.
- Address already in use → remediation names `--port` and stopping the occupant.

Not used as an HTTP 5xx type name; HTTP uses the JSON envelope in
[contracts/http-api.md](contracts/http-api.md).

## 3. Opaque Model Record

### Purpose

One row in `GET /v1/models`.

### Fields

- `id: str` — Opaque `domain/size` alias, LLM domain only (for example `llm/small`).
- `object: str` — Always `model`.
- `owned_by: str` — Always `ceia-aisdk`.
- `created: int` — Unix timestamp or `0`.

### Invariants

- No Hugging Face repository, URL, SHA-256, or filename.
- MUST NOT claim tool calling when the catalog alias lacks `tool_use`.
- Listing does not create an `LLM` or touch the weight cache.

## 4. Chat Completion Request

### Purpose

Stateless OpenAI-shaped generation request.

### Fields (accepted)

- `model: str` — Opaque alias; resolved through the registry (`llm/small`, `llm/small@N`,
  unqualified size with domain `llm`).
- `messages: list[ChatMessage]` — At least one message.
- `stream: bool` — Default `false`.
- `temperature: float` — Default `0.8`.
- `max_tokens: int` — Default `512`.
- `seed: int | None` — Optional; forwarded to `LLM`.
- `tools: list[ToolDeclaration] | None` — OpenAI function tools; accepted when the alias
  declares `tool_use`.
- `tool_choice: str | object | None` — Optional; `none` / `auto` / named function.

### ChatMessage

- `role: str` — `system`, `user`, `assistant`, or `tool`.
- `content: str | None` — P0 text. Structured/image parts are a P1 refusal.
- `tool_calls: list[ToolCall] | None` — On assistant messages that requested tools.
- `tool_call_id: str | None` — Required on `role: tool`.

### Rejected in this increment

- Image parts / `image_url` → 400 vision not available.
- `n` not equal to 1 → 400.
- `tools` on an alias without `tool_use` → 400 / `CapabilityError`.

### Invariants

- The server does not append the request to any stored session.
- A later request sees prior turns only if the client resends them in `messages`.

## 5. Chat Completion Response

### Purpose

OpenAI-compatible success body or SSE stream.

### Non-stream fields

- `id`, `object=chat.completion`, `created`, `model` (echo opaque alias).
- `choices[0].message.role=assistant`.
- `choices[0].message.content` nonempty on a text happy path; MAY be null when `tool_calls` is
  set.
- `choices[0].message.tool_calls` when the model requested tools.
- `choices[0].finish_reason` is `stop` (text) or `tool_calls`.
- `usage` object present; token counts MAY be zero.

### Stream

Ordered SSE `data:` JSON chunks (`object=chat.completion.chunk`) plus terminal `data: [DONE]`.
Text happy path: at least one content delta. Tool-call happy path: OpenAI-shaped
`delta.tool_calls` that assemble to the same calls as the non-stream body.

## 6. Model Pool Entry

### Purpose

Reuse one non-thread-safe `LLM` per canonical alias.

### Fields

- `alias: str` — Canonical `domain/size@N`.
- `instance: LLM`
- `lock` — Exclusive generation/construction lock for this alias.

### Invariants

- First use constructs the instance (registry obtain + load).
- Concurrent HTTP handlers never call generation on the same instance without the lock.
- No `Session` is stored on the entry.

### Failures

Mapped from existing SDK errors (`ModelNotFoundError`, `DownloadError`, `DeviceError`,
`GenerationError`, `CapabilityError` when `tools` are passed to an alias without `tool_use`).

## 7. Admission Queue

### Purpose

Bound waiting work so overload is visible.

### Fields

- `max_waiters: int` — Constant **8**.
- `waiters: int` — Current requests waiting for an alias lock.

### Transitions

1. Request arrives and the alias lock is free → acquire, `waiters` unchanged, generate.
2. Lock busy and `waiters < 8` → increment waiters, wait, decrement, acquire, generate.
3. Lock busy and `waiters >= 8` → HTTP 429, do not wait.

In-flight holders are not waiters. Each alias allows at most one in-flight generation.

## 8. HTTP Error Envelope

### Purpose

Stable JSON for every serving-surface failure.

### Fields

- `error.message: str` — English explanation, no traceback, no catalog URL, no prompt dump
  required (must not include message bodies).
- `error.type: str` — Machine type (`invalid_request_error`, `invalid_api_key`,
  `not_implemented_error`, `overloaded_error`, …).
- `error.code: str | null`
- `error.remediation: str` — Nonempty next action (HTTP analog of `AISDKError.remediation`).

## 9. Tool Call and Completion Result

### Purpose

Express one generate step that is either text or tool calls, without breaking `LLM.chat` →
`str`.

### ToolCall fields

- `id: str` — Client-echoed identifier (`tool_call_id` on the next `role: tool` message).
- `name: str` — Function name from the tool schema.
- `arguments: str` — JSON object encoded as a string (OpenAI wire form).

### CompletionResult fields

- `content: str | None` — Assistant text when the model did not request tools.
- `tool_calls: tuple[ToolCall, ...] | None` — When the model requested tools.
- Exactly one of `content` (nonempty) or nonempty `tool_calls` on a successful generate.

### Invariants

- Serve does not execute `ToolDeclaration.handler`.
- Passing tools to an alias without `tool_use` is `CapabilityError` before generate.

## 10. Adaptive Capability

### Purpose

Decide P1 route behavior without blocking P0.

### Fields

- `embeddings_available: bool` — `ceia_aisdk.rag` (or successor embeddings module) importable.
- `voice_available: bool` — voice module importable.
- `vision_available: bool` — vision module importable.

### Behavior

- Module false → reserved route 501 or vision-in-chat 400 as in the HTTP contract.
- Module true → server MAY implement forwarding in a later increment; not a `0.2.0` gate.
- Tool calls are not adaptive: they are P0 on chat completions via library `complete`.
