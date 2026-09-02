# Python API Contract: OpenAI-Compatible Server

**Feature**: `004-openai-server`
**Stability**: Public contract for PRD-06, consumed by PRD-07

This contract extends
[001-sdk-foundations/contracts/python-api.md](../../001-sdk-foundations/contracts/python-api.md),
[002-model-registry/contracts/python-api.md](../../002-model-registry/contracts/python-api.md),
and [003-llm-module/contracts/python-api.md](../../003-llm-module/contracts/python-api.md).

## Package Root

`ceia_aisdk.__init__` MUST NOT import `ceia_aisdk.server`, FastAPI, or uvicorn.

It MAY re-export `ServerError` from `ceia_aisdk.errors` the same way it re-exports
`GenerationError`.

`import ceia_aisdk` still finishes within the p95 200 ms reference target, makes no network
call, and MUST NOT leave `fastapi`, `uvicorn`, or `llama_cpp` in `sys.modules`.

## Errors

### `ServerError`

Direct subclass of `AISDKError`. Raised for serve-process failures that happen before or
instead of a successful bind:

- `[server]` extra missing (FastAPI or uvicorn import failure);
- bind address already in use or otherwise unavailable.

Contract:

- `.remediation` is nonempty English text.
- Missing extra remediation mentions `ceia-aisdk[server]`.
- Bind remediation mentions `--port` and stopping the occupant.
- String conversion does not include a Python traceback.

HTTP handlers MUST NOT leak `ServerError` as a traceback; in-process `create_app` tests use
HTTP status mapping from [http-api.md](http-api.md) for request errors.

## Server Module

Public module: `ceia_aisdk.server`.

Importing this module requires the `[server]` extra. Without it, the import raises
`ServerError` (or a wrapped import error that the CLI turns into `ServerError`).

```python
def create_app(
    *,
    token: str | None = None,
    cors_open: bool = False,
    debug: bool = False,
) -> Any: ...
```

`Any` is the FastAPI application object. Tests treat it as an ASGI app.

Contract:

- `create_app()` MUST NOT bind a socket. Binding is the CLI/`uvicorn` responsibility.
- Default `token=None` means no auth.
- Default `cors_open=False` means localhost-only CORS.
- `debug=True` is the only in-process switch that may log message bodies.
- The app exposes the routes in [http-api.md](http-api.md).
- Constructing the app MUST NOT load `llama_cpp` or construct an `LLM`. First chat request
  may do both, as in the library.

No other public types are required in this increment. Pool, admission queue, and message
translation are private.

## LLM Surface

This feature MUST NOT break `LLM.chat` / `.stream` / `.session` (`str` / `Iterator[str]`).

It MUST add the public one-step completion and types in
[tools.md](tools.md): `ToolCall`, `CompletionResult`, `LLM.complete` (and `AsyncLLM.complete`
when that class is present). The server maps `/v1/chat/completions` onto `complete`. It MUST
NOT execute `ToolDeclaration.handler`.

`from ceia_aisdk.llm import LLM, ToolCall, CompletionResult` MUST NOT load `llama_cpp`.

## Out of Scope

- Public async server client.
- Embedding FastAPI types in `ceia_aisdk.__init__`.
- A programmatic `serve_forever()` public helper (CLI is the supported start path).
