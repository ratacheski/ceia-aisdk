# HTTP API Contract: OpenAI-Compatible `/v1`

**Feature**: `004-openai-server`
**Base URL**: `http://127.0.0.1:11434/v1` (defaults)

Clients SHOULD set OpenAI `base_url` to that value (including `/v1`). The official Python
`openai` client MUST complete a chat on the happy path.

## Common rules

- JSON errors use the envelope in [data-model.md](../data-model.md) §8. No Python traceback in
  the body.
- When `--token` is set, all routes below require a matching Bearer token (401 otherwise).
- Default CORS allows only localhost origins. `--cors` allows any origin.
- No native TLS.

## `GET /v1/models`

**P0.** After ready, MUST return within 2 seconds.

Response `200`:

```json
{
  "object": "list",
  "data": [
    {
      "id": "llm/small",
      "object": "model",
      "created": 0,
      "owned_by": "ceia-aisdk"
    }
  ]
}
```

- `id` values are opaque `llm/<size>` aliases from the active catalog.
- MUST NOT include Hugging Face names or URLs.
- MUST NOT claim tool calling for an alias that lacks catalog `tool_use`.

## `POST /v1/chat/completions`

**P0.** Request JSON minimum:

```json
{
  "model": "llm/small",
  "messages": [{"role": "user", "content": "Say only: ok"}],
  "stream": false,
  "temperature": 0.8,
  "max_tokens": 512
}
```

Accepted optional: `seed` (integer), `tools`, `tool_choice`.

Behavior:

- Non-stream text → `200` `application/json` chat.completion with nonempty
  `choices[0].message.content`.
- Non-stream tool call → `200` with `choices[0].message.tool_calls` and
  `finish_reason` `tool_calls`. The server does not execute the function.
- Follow-up MAY include `role: "tool"` messages on this same route.
- `stream: true` → `200` `text/event-stream` with ≥ 1 `data:` JSON chunk (text `delta.content`
  or `delta.tool_calls`) and `data: [DONE]`.
- Text generation matches shipped `LLM.chat` for the same prompt under documented equivalence.
- Stateless: no server-side history.

Errors: see research mapping (400 validation/vision/`tools` on a non-`tool_use` alias, 404
unknown alias, 429 queue, 503 obtain/device, 401 auth). See [tools.md](tools.md).

## Reserved module routes (P1, not a `0.2.0` gate)

These paths MUST exist and MUST NOT traceback:

| Method | Path | Absent module (`0.2.0`) | Present later |
|--------|------|-------------------------|---------------|
| POST | `/v1/embeddings` | **501** | MAY embed |
| POST | `/v1/audio/transcriptions` | **501** | MAY transcribe |
| POST | `/v1/audio/speech` | **501** | MAY synthesize |

Chat-level vision refusal (P1, tests required so P0 does not crash):

| Request feature | Status | Message (English, stable sense) |
|-----------------|--------|----------------------------------|
| Image / `image_url` content parts | **400** | vision is not available |
| `tools` on an alias without `tool_use` | **400** | capability / choose a `tool_use` alias |

## Unimplemented OpenAI product surfaces

`/v1/assistants`, `/v1/batches`, `/v1/files`, `/v1/fine-tuning` (and similar) → **404** with
the standard error envelope. No traceback.

## Overload

When the waiter queue is full (8), `POST /v1/chat/completions` returns **429** with
`error.type` such as `overloaded_error` and nonempty `error.remediation`.

## Auth

| `--token` | Header | Status |
|-----------|--------|--------|
| unset | any or none | not rejected for auth |
| set | missing / wrong / non-Bearer | **401** |
| set | `Authorization: Bearer <token>` | auth passes |

## CORS

| Mode | Browser origin `http://example.com` | `http://localhost:3000` or `http://127.0.0.1:3000` |
|------|--------------------------------------|-----------------------------------------------------|
| default | not allowed | allowed |
| `--cors` | allowed | allowed |

## Test Contract

Automated tests MUST verify models list opacity, non-stream chat, SSE `data:` chunk, tool-call
JSON and `role: tool` follow-up, 401, CORS headers or preflight, 429 after 8 waiters, 501
reserved routes, 400 vision and 400 tools-without-capability, 404 unknown OpenAI path, and an
official-client or httpx happy path against `/v1`.
