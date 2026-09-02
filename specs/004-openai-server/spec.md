# Feature Specification: OpenAI-Compatible Local Server

**Feature Branch**: `main` (no branch was created; there is no `before_specify` hook)

**Created**: 2026-09-02

**Status**: Draft

**Input**: PRD-06 (`docs/prd/06-server.md`) and decisions ratified in the PRD program on 2026-09-01, with the explicit delivery constraint that this increment depends only on already shipped PRDs 00–02 (`ceia-aisdk==0.1.0`) and must not wait for voice, vision, or RAG

## User Scenarios & Testing *(mandatory)*

This feature has two delivery bands. **P0** (SpecKit P1 stories) is the gate for the second public product: a developer can install the server extra, start a localhost OpenAI-compatible endpoint, list opaque model aliases, complete chat with and without streaming, run the OpenAI tool-call round trip on that same chat route, protect the bind surface, and survive a full request queue with a documented overload response. Completing tool calls requires finishing the library surface that PRD-02 left incomplete (`LLM.chat` stays a string; a new one-step completion returns text or tool calls). **P1** (SpecKit P2 story) must not block that gate: embeddings, audio, and vision image parts return a stable, traceback-free refusal while those modules are absent. This increment publishes **`ceia-aisdk==0.2.0`** with the `[server]` extra; it does not wait for PRDs 03–05 or 07.

### User Story 1 - Start a Local OpenAI-Compatible Server (Priority: P1)

As a developer, I want to run `ceia-aisdk serve` after installing the `[server]` extra so that any OpenAI-compatible client can talk to the SDK on this machine without rewriting application code.

**Why this priority**: A Python library alone cannot compete with local serving products in the ecosystem. Continue, LibreChat, LangChain, and the official OpenAI client need an HTTP endpoint. This is the second public demo after first chat.

**Independent Test**: Install with the server extra, run `ceia-aisdk serve` with defaults, confirm a ready log with an absolute URL on `127.0.0.1:11434`, then repeat without the extra and when the port is already taken.

**Acceptance Scenarios**:

1. **Given** `ceia-aisdk==0.2.0` (or a release-candidate equivalent) with the `[server]` extra installed on Linux x86_64, **When** the developer runs `ceia-aisdk serve` with no bind flags, **Then** the process listens on `127.0.0.1:11434` and the ready log contains an absolute URL that uses that host and port.
2. **Given** the extra is installed, **When** the developer passes `--host` and `--port`, **Then** the process binds to the requested host and port instead of the defaults.
3. **Given** a supported installation **without** the `[server]` extra, **When** the developer runs `ceia-aisdk serve` or inspects command help, **Then** the command is discoverable and the failure or help text explains how to install `ceia-aisdk[server]` rather than crashing with an unreadable traceback.
4. **Given** another process already occupies the chosen port (for example a local serving product using 11434), **When** `serve` starts, **Then** the process fails with a public error whose remediation tells the operator to change `--port` or stop the occupant, and does not hang.
5. **Given** default flags, **When** the process starts, **Then** it MUST NOT bind to all interfaces (`0.0.0.0`). An explicit `--host` may select a non-default address; the default remains loopback.
6. **Given** the process is ready, **When** an operator reads the ready log at the default log level, **Then** it does not print chat message contents.

---

### User Story 2 - List Models and Complete Chat (Priority: P1)

As a developer, I want `GET /v1/models` and `POST /v1/chat/completions` (plain and streamed) so that I can point an OpenAI-compatible client at the SDK and replace a cloud or third-party local endpoint for chat.

**Why this priority**: Listing and chat are the minimum drop-in contract. Without them, starting the server has no ecosystem value. Streaming is required because many clients default to it.

**Independent Test**: After ready, list models, complete a non-stream chat, complete a streamed chat, and drive the same prompt through the official OpenAI Python client (or an HTTP client using the same base URL) against `http://127.0.0.1:11434/v1`.

**Acceptance Scenarios**:

1. **Given** the server is ready, **When** a client calls `GET /v1/models`, **Then** the response arrives within 2 seconds, lists only opaque catalog aliases such as `llm/small` (and other curated LLM aliases the registry already exposes), and never includes Hugging Face repository names, download URLs, or other non-alias identifiers.
2. **Given** `POST /v1/chat/completions` with at least `model`, `messages`, and the documented optional fields `stream`, `temperature`, and `max_tokens`, **When** `stream` is omitted or false, **Then** the response is a chat-completion JSON body whose message content is nonempty text and matches the behavior of the shipped PRD-02 `LLM` for the same prompt (nonempty text; tests may cap tokens).
3. **Given** the same route with `stream: true`, **When** the client reads the response, **Then** the body is a server-sent event stream with at least one `data:` chunk, concatenated content is nonempty, and the observable generation matches PRD-02 `LLM` streaming for the same prompt under the same documented equivalence rules (exact match under fixed seed and temperature, or nonempty chunks when the backend is not bit-stable).
4. **Given** `base_url` pointing at `http://127.0.0.1:11434/v1` and a cataloged LLM alias already local or obtainable as in PRD-02, **When** a developer uses the official OpenAI Python client or an equivalent HTTP client to complete a chat, **Then** the call succeeds without a custom request schema.
5. **Given** two successive chat requests that would form a conversation if the server stored history, **When** each request is sent independently, **Then** the server remains stateless: it does not persist conversation history to disk or reuse prior turns unless the client resends them in `messages`.
6. **Given** `GET /v1/models`, **When** a client inspects model metadata, **Then** the listing MUST NOT claim tool calling for an alias that lacks catalog `tool_use`. Aliases that declare `tool_use` MAY be documented as tool-capable without adding Hugging Face names.

---

### User Story 3 - Keep the Default Bind Surface Local (Priority: P1)

As an operator, I want the server to stay on loopback by default, to require a Bearer token when I opt in, and to restrict cross-origin access so that running `serve` does not expose the GPU or prompts on the local network.

**Why this priority**: The default bind is a safety gate, not a later hardening pass. A hobbyist who copies a one-line start command must not publish inference to the LAN.

**Independent Test**: Confirm default bind is loopback, default cross-origin policy allows only localhost origins, a missing Bearer header returns 401 when `--token` was set, and `--cors` relaxes the origin restriction.

**Acceptance Scenarios**:

1. **Given** `ceia-aisdk serve` with no `--host`, **When** the process is ready, **Then** it accepts connections on `127.0.0.1` and the documented default port is 11434.
2. **Given** no `--token` flag, **When** a client calls models or chat, **Then** the request is not rejected for missing authentication.
3. **Given** `--token` was provided at start, **When** a request arrives without `Authorization: Bearer <token>` or with the wrong token, **Then** the server returns 401 in 100% of those cases, with a stable JSON body and no traceback.
4. **Given** `--token` was provided, **When** a request presents the matching Bearer token, **Then** authorization does not by itself block models or chat.
5. **Given** default flags (no `--cors`), **When** a browser origin other than localhost attempts a cross-origin request, **Then** the server does not grant that origin access; only localhost origins are allowed.
6. **Given** `--cors` is set, **When** a non-localhost origin is presented, **Then** the origin restriction is relaxed as documented for that flag.

---

### User Story 4 - Queue Overflow Returns a Clear Overload (Priority: P1)

As a developer running a single-machine server, I want concurrent chat requests to share a small pool and queue so that overload is visible as HTTP 429 after a documented maximum queue, rather than unbounded memory growth or a hung client.

**Why this priority**: Shipped LLM instances are not thread-safe. The server must serialize or isolate work. Backpressure is part of the P0 contract, not a later operations feature.

**Independent Test**: Issue more concurrent chat requests than the pool can run at once, fill the documented queue of 8, and observe 429 with a stable JSON body; confirm queued work still completes in order without writing history to disk.

**Acceptance Scenarios**:

1. **Given** the server is ready, **When** chat requests target a cataloged alias, **Then** the server uses a pool that keeps one default in-use instance for that requested alias and does not treat a single instance as safe for concurrent generation.
2. **Given** a request that cannot start immediately because the instance is busy, **When** the waiting queue has fewer than 8 entries, **Then** the request waits in the queue instead of failing immediately.
3. **Given** the waiting queue already holds 8 requests, **When** another chat request arrives, **Then** the server returns 429 with a stable JSON body, no traceback, and nonempty remediation in the public error contract or documented HTTP body.
4. **Given** any successful or failed request, **When** the server handles it, **Then** it does not write conversation history to disk.

---

### User Story 5 - Publish 0.2.0 with the Server Extra (Priority: P1)

As an external developer, I want to `pip install ceia-aisdk[server]` from the public index so that the serving increment exists as the next minor of the same product, not a second package.

**Why this priority**: The program publishes one project on the public index. First chat was `0.1.0`. This feature is the next minor and the first version that declares the `[server]` extra.

**Independent Test**: Inspect package metadata and the public index page for `ceia-aisdk==0.2.0`, installability of `[server]`, absence of model weights, Linux-only classifiers, and documentation for serve, bind conflict, token, CORS, and reverse-proxy TLS.

**Acceptance Scenarios**:

1. **Given** completion of the P0 stories, **When** the release is published, **Then** `ceia-aisdk==0.2.0` is available on the public index as the same project, not a new distribution name.
2. **Given** that version, **When** a developer installs `ceia-aisdk[server]`, **Then** the extra is declared and installable; `[server]` MUST NOT have been required in `0.1.0`.
3. **Given** the published wheel and source distribution, **When** their contents are inspected, **Then** they do not include model weight files, a desktop binary, or an installer.
4. **Given** the project page and CLI help for this version, **When** a developer reads them, **Then** they document `ceia-aisdk serve`, default `127.0.0.1:11434`, opaque aliases, optional token, default CORS, queue limit 8 and 429, port-conflict remediation, OpenAI `tools` / `tool_calls` on the same chat route (client executes tools; the server does not), and that TLS is provided by an external reverse proxy, not by this process.
5. **Given** `ceia-aisdk --help` and `ceia-aisdk serve --help`, **When** they are shown, **Then** `serve` is discoverable from root help, and serve help describes purpose, every flag, required status, defaults, constraints, and at least one executable example.

---

### User Story 6 - Tool Calls on the Same Chat Route (Priority: P1)

As a developer pointing an agent at localhost, I want `POST /v1/chat/completions` to accept OpenAI `tools` and return `tool_calls` so that my client can execute the function and send the result back on the same route. I also want the Python library to expose that one-step result, because the server cannot invent tool calls the model API does not return.

**Why this priority**: Tools are part of chat completions, not a later module. Agents do not need a second URL. PRD-02 left the library loop unfinished (`ToolDeclaration` and a capability gate only; `chat` still returns only text). This increment completes that library step and maps it onto the OpenAI chat contract. Voice and vision remain out.

**Independent Test**: From the library, complete a messages+tools turn and observe either assistant text or structured tool calls without breaking `LLM.chat` → `str`. From the server, send `tools` for an alias that declares `tool_use`, receive OpenAI `tool_calls`, then send a follow-up with `role: "tool"` and receive a final reply. Sending `tools` to an alias without `tool_use` returns 400 / `CapabilityError`. The server never runs the tool.

**Acceptance Scenarios**:

1. **Given** an alias whose catalog capabilities include `tool_use`, **When** a library caller requests a one-step completion with tool declarations and no auto-handler loop, **Then** the result is either nonempty assistant text or one or more structured tool calls (name, arguments, id). `LLM.chat` still returns `str` and MUST NOT change its public signature.
2. **Given** the same alias on `POST /v1/chat/completions` with OpenAI-schema `tools`, **When** the model requests a tool, **Then** the JSON body uses `choices[0].message.tool_calls` and `finish_reason` `tool_calls`. The process MUST NOT execute the function and MUST NOT require a `handler`.
3. **Given** a prior assistant `tool_calls` turn, **When** the client sends a new request that includes `role: "tool"` messages (and any assistant tool-call messages the client echoes), **Then** the server uses that payload for one generation and returns text or further tool calls. It still stores nothing on disk.
4. **Given** `stream: true` and a tool-call result, **When** the client reads SSE, **Then** chunks include OpenAI-shaped `delta.tool_calls` (or an equivalent documented stream that the official client can assemble) and end with `data: [DONE]`.
5. **Given** an alias that does not declare `tool_use`, **When** the client or library passes `tools`, **Then** the failure is `CapabilityError` in the library and HTTP 400 on the server, with nonempty remediation, and tools are not silently ignored.
6. **Given** `GET /v1/models`, **When** an alias lacks `tool_use`, **Then** the listing does not claim tool calling for that alias.

---

### User Story 7 - Adaptive Routes for Modules That Are Not in This Slice (Priority: P2)

As a developer, I want embeddings, audio, and vision image parts on this server only when those modules already exist so that the process can grow later without blocking localhost chat, and so missing capabilities fail with a stable status instead of a crash.

**Why this priority**: This is product P1. Voice, vision, and RAG are **not** dependencies of this increment. Tool calls are User Story 6 (P0). Adaptive refusals keep the remaining OpenAI URL space predictable.

**Independent Test**: Call embeddings and audio routes and send vision image parts in chat; assert stable JSON 404 or 501 (module routes) or 400 (vision in chat) with no traceback while those modules remain unshipped.

**Acceptance Scenarios**:

1. **Given** the embeddings module is not present in this installation, **When** a client calls `POST /v1/embeddings`, **Then** the server returns a stable JSON 404 or 501, never a traceback, and does not block P0 chat or tools.
2. **Given** the voice module is not present, **When** a client calls `POST /v1/audio/transcriptions` or `POST /v1/audio/speech`, **Then** the server returns a stable JSON 404 or 501 with no traceback.
3. **Given** the vision module is not present, **When** a chat request includes image URL or base64 image parts, **Then** the server returns 400 with a stable JSON body that states vision is not available, and no traceback.
4. **Given** a later installation where embeddings, voice, or vision **are** already present, **When** the corresponding client request is in the supported subset, **Then** the server MAY forward it through that module; this must not be required to publish `0.2.0`.
5. **Given** assistants, batches, files, or fine-tune URLs, **When** they are requested, **Then** the server does not implement them; a 404 (or equivalent documented not-found) with stable JSON and no traceback is sufficient.

---

### Edge Cases

- Default port 11434 is already bound (local serving product or another `serve`); start must fail fast with remediation naming `--port` or stopping the occupant.
- `--host 0.0.0.0` is passed explicitly; the default remains loopback, but an explicit host is honored. Documentation must warn that this exposes the process beyond the machine.
- `--token` is set and the client sends `Authorization` with a non-Bearer scheme or a truncated token; result is 401.
- `--token` is set and `GET /v1/models` is called without a header; result is 401 (auth applies to the documented serving surface, not only chat).
- CORS preflight from a non-localhost origin with default flags is denied; with `--cors` it is allowed as documented.
- Request body is missing `model` or `messages`; the server returns a 4xx stable JSON error, not a 500 traceback.
- `model` is an unknown alias; the failure follows the registry contract (`ModelNotFoundError` mapped to a stable HTTP error with remediation), not a generic 500.
- Offline mode is on and the alias is uncached; chat fails using the existing obtain error, mapped to a stable HTTP error, without hanging on the network.
- Stream is aborted by the client mid-response; the server must not crash and must not persist partial history.
- Queue depth is exactly 8 waiters plus one in-flight; the next request is 429; when a slot frees, a queued request proceeds.
- Concurrent requests for two different aliases; the documented pool is one default instance per requested alias. Cross-alias isolation MUST NOT require a shared unsafe concurrent call on one instance.
- Chat `messages` contain prior turns supplied by the client; the server uses that payload for the turn and still does not store it after the response.
- Default log level must not print `messages`; a documented debug flag may allow it when explicitly enabled.
- Client sends vision parts; 400 vision not available, even if `tools` are also present and valid.
- Client sends `tools` to an alias without `tool_use`; 400 / `CapabilityError`, not a 500.
- Client sends `role: "tool"` without a preceding assistant `tool_calls` in the same request `messages`; 400 with stable JSON.
- Library `LLM.chat` is still invoked while tools are configured on the instance; it remains a text convenience and MUST NOT start executing HTTP-style tool calls as a breaking change to its `str` return.
- `[server]` extra is missing but the base package is installed; `serve` explains the extra rather than importing a broken optional stack as an unhandled exception.
- Happy-path chat JSON must be valid for the official client; unknown OpenAI fields that are out of scope are ignored or rejected with 4xx, never by crashing.
- IPv6 loopback versus `127.0.0.1`; the documented default is IPv4 loopback `127.0.0.1`.
- Process is stopped while requests are queued; in-flight work may fail, but shutdown must not write conversation files.

## Requirements *(mandatory)*

### Functional Requirements

P0 requirements (User Stories 1–6) are the `0.2.0` gate. P1 requirements (User Story 7, **FR-032** through **FR-034**, **FR-036**, **FR-037**) MUST NOT block that gate and MUST NOT wait for voice, vision, or RAG to exist.

- **FR-001**: The package MUST declare an optional extra named `[server]` in this increment; installing `ceia-aisdk[server]` MUST be sufficient to run the serve command.
- **FR-002**: Root CLI help MUST list `serve`. `ceia-aisdk serve --help` MUST describe purpose, `--host`, `--port`, `--token`, `--cors`, every other public flag, required status, defaults, constraints, and at least one executable example.
- **FR-003**: `ceia-aisdk serve` without bind flags MUST listen on host `127.0.0.1` and port `11434`.
- **FR-004**: `--host` MUST default to `127.0.0.1` and `--port` MUST default to `11434`. The default bind MUST NEVER be `0.0.0.0`.
- **FR-005**: When the process is ready, it MUST log an absolute URL for the listening address.
- **FR-006**: When the `[server]` extra is not installed, `serve` MUST explain how to install `ceia-aisdk[server]` and MUST NOT fail with an unhandled traceback.
- **FR-007**: When the requested bind address is unavailable, start MUST fail with a public error whose nonempty remediation mentions changing `--port` or stopping the occupant (including the case of another local server on 11434).
- **FR-008**: `GET /v1/models` MUST return within 2 seconds after ready and MUST list only opaque aliases, never Hugging Face names or download URLs.
- **FR-009**: `GET /v1/models` MUST NOT claim tool calling for an alias that lacks catalog `tool_use`.
- **FR-010**: `POST /v1/chat/completions` MUST accept at least `model`, `messages`, `stream`, `temperature`, `max_tokens`, and, when the alias allows it, OpenAI-schema `tools` and `tool_choice`.
- **FR-011**: `model` in chat and in the models list MUST be an opaque alias (`llm/small` and other cataloged LLM aliases). Hugging Face identifiers MUST NOT be required or returned.
- **FR-012**: Non-stream chat MUST return nonempty assistant text that reproduces shipped PRD-02 `LLM` behavior for the same prompt under the same documented equivalence rules.
- **FR-013**: Chat with `stream: true` MUST respond as server-sent events with at least one `data:` chunk and nonempty concatenated text, reproducing shipped PRD-02 `LLM` stream behavior under the same equivalence rules.
- **FR-014**: The official OpenAI Python client or an equivalent HTTP client MUST be able to complete a chat using `base_url=http://127.0.0.1:11434/v1` on the happy path.
- **FR-015**: Happy-path chat responses MUST match the OpenAI chat-completion JSON shape enough for that client (non-stream object; stream as SSE `data:` lines).
- **FR-016**: The server MUST be stateless across requests except for the in-memory model pool: it MUST NOT persist conversation history to disk.
- **FR-017**: Requests MUST NOT require authentication unless `--token` was provided at start.
- **FR-018**: When `--token` was provided, every request lacking a matching `Authorization: Bearer` token MUST return 401 with a stable JSON body and no traceback.
- **FR-019**: Default cross-origin policy MUST allow only localhost origins. `--cors` MUST relax that restriction as documented.
- **FR-020**: The server MUST keep a pool with one default in-use instance per requested alias and MUST serialize or isolate generation so a non-thread-safe LLM instance is never used concurrently.
- **FR-021**: The waiting queue MUST hold at most 8 requests. A chat request that would exceed that maximum MUST return 429 with a stable JSON body and no traceback.
- **FR-022**: At default log level, the server MUST NOT log `messages` contents. Logging of message bodies MUST require an explicit debug flag.
- **FR-023**: This feature MUST publish `ceia-aisdk==0.2.0` to the public index as the next minor of the same project.
- **FR-024**: The `[server]` extra MUST appear in `0.2.0` and MUST NOT have been part of the `0.1.0` user contract.
- **FR-025**: Published wheel and source distribution MUST NOT embed model weights, a binary, or an installer.
- **FR-026**: User documentation for this increment MUST cover install of `[server]`, `ceia-aisdk serve`, default bind, opaque aliases, stream versus non-stream chat, OpenAI `tools` / `tool_calls` on the same chat route, that the client executes tools, optional token, CORS, queue depth 8 and 429, port-conflict remediation, reverse-proxy TLS, Linux x86_64, and that voice, vision, RAG, and the app launcher are out of this slice.
- **FR-027**: `ceia-aisdk doctor` MUST continue to report installed extras; after this extra is installed, `[server]` MUST be visible as present rather than absent or reserved-only.
- **FR-028**: All public failures on this serving surface MUST use stable JSON bodies with no Python traceback in the HTTP response. Mapped SDK errors MUST preserve nonempty remediation.
- **FR-029**: Prompts and completions MUST remain on the local machine; this feature MUST NOT send message content to a telemetry endpoint.
- **FR-030**: Native TLS, a custom web UI, multi-user authentication, assistants, batches, files, fine-tune, and the app launcher MUST NOT ship in this feature.
- **FR-031**: This feature MUST depend only on shipped foundations, registry, and LLM (`ceia-aisdk==0.1.0`). It MUST NOT require voice, vision, or RAG to merge or publish `0.2.0`.
- **FR-032** (P1, MUST NOT block `0.2.0`): If embeddings are not present, `POST /v1/embeddings` MUST return stable JSON 404 or 501 with no traceback. If embeddings are already present, the route MAY serve them.
- **FR-033** (P1, MUST NOT block `0.2.0`): If voice is not present, `POST /v1/audio/transcriptions` and `POST /v1/audio/speech` MUST return stable JSON 404 or 501 with no traceback. If voice is already present, those routes MAY serve them.
- **FR-034** (P1, MUST NOT block `0.2.0`): If vision is not present, chat requests that include image URL or base64 parts MUST return 400 with stable JSON and no traceback. If vision is already present, the server MAY forward those parts.
- **FR-035**: The library MUST provide a one-step completion (messages plus optional tools) that returns either assistant text or structured tool calls, without changing the `LLM.chat` → `str` signature.
- **FR-036** (P1, MUST NOT block `0.2.0`): Adaptive module routes MUST NOT change P0 models, chat, or tool-call behavior when voice, vision, or RAG are missing.
- **FR-037** (P1, MUST NOT block `0.2.0`): Assistants, batches, files, and fine-tune URLs MUST remain unimplemented (stable 404 or equivalent), with no traceback.
- **FR-038**: For an alias that declares `tool_use`, `POST /v1/chat/completions` with OpenAI `tools` MUST return OpenAI-shaped `tool_calls` when the model requests a tool, and MUST accept a follow-up with `role: "tool"` on the same route.
- **FR-039**: The serve process MUST NOT execute tool handlers. The client executes the function and resends the result.
- **FR-040**: Passing `tools` to an alias that does not declare `tool_use` MUST raise `CapabilityError` in the library and MUST return HTTP 400 on the server, with nonempty remediation.
- **FR-041**: Streamed tool-call responses MUST be valid SSE that a client can assemble into the same `tool_calls` as the non-stream body.

### Scope Boundaries

Included in this feature:

- Optional `[server]` extra and `ceia-aisdk serve`.
- Default loopback bind `127.0.0.1:11434`, `--host`, `--port`, `--token`, `--cors`.
- OpenAI-compatible `GET /v1/models` (opaque aliases only).
- OpenAI-compatible `POST /v1/chat/completions` with and without SSE streaming, matching shipped LLM text behavior.
- OpenAI `tools` / `tool_calls` / `role: "tool"` on that same route, plus the library one-step completion that emits tool calls.
- Optional Bearer token, default localhost-only CORS, in-memory pool, queue of 8, HTTP 429 when full.
- Bind-error remediation when the port is taken.
- Public index publication of `ceia-aisdk==0.2.0`.
- Stable refusals for embeddings, audio, and vision parts when those modules are absent.

Explicitly excluded:

- Waiting for voice (PRD-03), vision (PRD-04), or RAG (PRD-05) before shipping P0.
- Implementing embeddings, audio, or vision as a merge gate for `0.2.0`.
- Executing tool functions inside `serve` (the client runs them).
- Breaking `LLM.chat` so that it no longer returns `str`.
- OpenAI assistants, batches, files, and fine-tune APIs.
- Multi-user authentication, accounts, or API-key management beyond a single optional process token.
- Native TLS inside `serve` (reverse proxy is the documented path).
- Custom web UI.
- App launcher and Open WebUI packaging (PRD-07).
- Redistributing the SDK as a binary; `[server]` is an extra of the same PyPI project.
- Binding to all interfaces by default.
- Persisting chat history on disk.
- Claiming tool calling on `/v1/models` for aliases that lack `tool_use`.
- Windows, Apple Silicon, ROCm, Vulkan, and non-PyPI channels.
- Changing the LLM launch default or the 15-minute first-chat KPI.

### Key Entities

- **Serve Process**: A local HTTP process started by `ceia-aisdk serve`, bound to one host and port, optionally holding a Bearer token and a CORS mode.
- **Server Extra**: The optional install group `[server]` that must be present to run the process; without it, the command tells the user how to install it.
- **Opaque Alias**: A cataloged model id such as `llm/small` returned by `/v1/models` and accepted as `model` in chat; never a Hugging Face repository name.
- **Chat Completion Request**: A stateless OpenAI-shaped payload (`model`, `messages`, optional `stream`, `temperature`, `max_tokens`, `tools`, `tool_choice`) that maps to one LLM generation.
- **Tool Call**: A named function invocation the model requested (id, name, arguments) for the client to execute.
- **One-Step Completion**: Library result that is either assistant text or tool calls for a single generate, used by the server and by Python callers who do not want an auto-handler loop.
- **Event Stream**: A streamed chat response delivered as server-sent `data:` chunks whose concatenation is the assistant text or the assembled `tool_calls`.
- **Model Pool**: In-memory set of LLM instances, one default in-use instance per requested alias, not safe for concurrent generation on the same instance.
- **Request Queue**: FIFO waiter list with maximum depth 8; overflow becomes HTTP 429.
- **Bearer Token**: Optional single shared secret presented as `Authorization: Bearer`; when configured, absence or mismatch is 401.
- **Adaptive Module Route**: An OpenAI URL that succeeds only if the corresponding shipped module exists; otherwise a stable 404/501 or, for vision in chat, 400.
- **Public Release 0.2.0**: The next minor of `ceia-aisdk` on the public index, adding `[server]` without embedding weights.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After `ceia-aisdk serve` reports ready on the default address, 100% of measured `GET /v1/models` calls return within 2 seconds and 100% of those bodies contain only opaque aliases (zero Hugging Face names).
- **SC-002**: 100% of measured non-stream `POST /v1/chat/completions` happy-path calls return nonempty assistant text that matches shipped LLM chat behavior for the same prompt under the documented equivalence rules.
- **SC-003**: 100% of measured `stream: true` happy-path calls deliver at least one `data:` chunk and nonempty concatenated text matching shipped LLM stream behavior under the same equivalence rules.
- **SC-004**: 100% of integration checks using the official OpenAI Python client or equivalent HTTP client with `base_url=http://127.0.0.1:11434/v1` complete a chat on the happy path.
- **SC-005**: 100% of default-start inspections show bind `127.0.0.1:11434` and not `0.0.0.0`. 100% of requests without a Bearer token while `--token` is set receive 401.
- **SC-006**: When the waiting queue is already at 8, 100% of additional chat requests receive 429 with a stable JSON body and no traceback.
- **SC-007**: 100% of start attempts against an occupied default port fail with nonempty remediation that mentions `--port` or stopping the occupant.
- **SC-008**: `ceia-aisdk==0.2.0` is present on the public index with an installable `[server]` extra; 100% of reviewed artifacts omit model weights and omit a binary or installer.
- **SC-009**: While voice, vision, and RAG are absent, 100% of embeddings and audio calls return stable 404 or 501, and 100% of chat requests that include vision image parts return 400, all without a traceback in the HTTP body.
- **SC-011**: 100% of library one-step completions with tools on a `tool_use` alias (live capable model or fake/recording) return either nonempty text or structured tool calls. 100% of matching `/v1/chat/completions` tool-call happy paths use the OpenAI `tool_calls` shape. 100% of `tools` requests against an alias without `tool_use` are `CapabilityError` / HTTP 400. 100% of those paths leave tool execution to the client.
- **SC-010**: In an evaluation with at least five representative developers on Linux x86_64, at least 90% can install the extra, start `serve`, and complete one chat from an OpenAI-compatible client on the first attempt by following the project documentation, without reading source code.

## Assumptions

- Foundations, registry, and LLM are already shipped as `ceia-aisdk==0.1.0`. This increment is the next minor (`0.2.0`) of the same project.
- Voice, vision, and RAG may be absent at merge time. P0 MUST NOT wait for them. P1 describes adaptive behavior so those URLs stay stable.
- This increment **completes** the library tool-call step that PRD-02 specified but did not finish (`ToolDeclaration` and the capability gate exist; `generate` still returns only text). `LLM.chat` remains `str`. A new one-step completion is the contract the server maps to OpenAI `tools` / `tool_calls`.
- The serve process does not run tool handlers. Optional Python handler loops on `ToolDeclaration` MAY remain a library convenience and MUST NOT be required for the HTTP path.
- Tiny CI GGUFs MAY be unable to emit a live tool call. Automated P0 coverage uses a fake backend or recording for the OpenAI shape; a live `get_weather` (or equivalent) on a cataloged `tool_use` alias remains a reference-machine checklist item.
- Maximum queue depth is **8**, as the value locked from PRD-06. Changing it later is a specification change.
- Overload policy is **429 after the queue is full**, not “wait with an undocumented timeout.”
- Default CORS allows only localhost origins; `--cors` is a boolean relax switch, not a free-form origin list, unless later documentation adds a list form without breaking the flag.
- A single optional `--token` is shared-secret protection for a local process, not multi-user auth.
- Port 11434 is an intentional drop-in versus a common local serving port; coexistence on the same port is not required.
- TLS terminates at a reverse proxy in front of loopback; this process does not terminate TLS.
- Chat equivalence with PRD-02 uses the same rules as that feature: nonempty text, optional substring checks, token caps in tests, and stream concatenation versus chat under fixed seed and temperature when the backend is stable enough.
- Automated CI MUST NOT download production multi-gigabyte weights. Server tests MAY use the tiny catalog fixture already used by the LLM feature.
- The `[server]` extra installs the HTTP serving stack named in PRD-06; extra name, CLI, and `/v1` routes are the user contract. Internal module layout is a planning concern.
- `doctor` already lists extras; this feature only needs `[server]` to appear when installed.
- Linux x86_64 remains the only supported platform. Python 3.11–3.13 remains the supported range.
- No conversation store, session cookie, or server-side thread id is provided; clients that need memory resend `messages`.
- The decisions ratified in the PRD program on 2026-09-01 and PRD-06 are the normative sources for this specification, except where this feature description explicitly ships the server before PRDs 03–05 and assigns version `0.2.0`.
- The ratified project constitution, version 1.0.0, governs this feature and all downstream SpecKit artifacts.

### Dependencies

- This feature depends on `001-sdk-foundations`: package identity, CLI, `AISDKError` with `.remediation`, `doctor` extra reporting, logging, and Linux-only metadata.
- This feature depends on `002-model-registry`: opaque aliases, catalog metadata, `ensure_local`, `ModelNotFoundError`, and offline obtain failures.
- This feature depends on `003-llm-module` / published `ceia-aisdk==0.1.0`: `LLM` chat and stream semantics, default `llm/small`, non-thread-safety, device/obtain errors, `ToolDeclaration`, and the `tool_use` capability gate. It **extends** that module with a one-step completion that can return tool calls.
- This feature does **not** depend on voice, vision, RAG, or the app launcher.
- Later app-launcher work depends on this serving contract existing on localhost with OpenAI-compatible chat.
- Production serve uses published `0.2.0` artifacts and cataloged aliases. Automated tests MUST still serve tiny fixtures locally.
