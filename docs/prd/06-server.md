# PRD 06 — OpenAI-compatible server mode

| Field | Value |
|---|---|
| ID | `PRD-06` |
| Status | Draft |
| Speckit Slug | `openai-server` |
| Depends on | PRD-02; exposes 03–05 if already merged |
| Unlocks | PRD 07; any ecosystem client |
| PyPI | Next minor + `[server]` extra in the same package. |
| Source Plan | Stage 7 |

---

### 1. Executive Summary

- **Problem Statement**: A Python library alone cannot compete with Ollama in the ecosystem. Without OpenAI-compatible HTTP, Continue, LibreChat, and LangChain cannot point to the SDK.
- **Proposed Solution**: The `ceia-aisdk[server]` extra with FastAPI/uvicorn, `ceia-aisdk serve`, OpenAI-compatible `/v1/*` routes, localhost binding, optional token, and an internal pool.
- **Success Criteria**:
  - `ceia-aisdk serve` (with the extra) listens on `127.0.0.1:11434`, and `GET /v1/models` returns only opaque aliases, never HF names, in ≤ 2 s after ready.
  - `POST /v1/chat/completions` without streaming and with `stream: true` (SSE) reproduce the behavior of the PRD 02 `LLM` for the same prompt (non-empty text; stream has ≥ 1 `data:` chunk).
  - The official Python `openai` client (or httpx) with `base_url=http://127.0.0.1:11434/v1` completes a chat in an integration test.
  - The default bind address is never `0.0.0.0`. A request without Bearer authentication when `--token` was provided → 401 in 100% of cases.
  - Routes for modules that are not installed or not implemented → 404 or 501 with a stable JSON body and no traceback.

---

### 2. User Experience & Functionality

- **User Personas**: hobbyist pointing an OpenAI client to localhost; Python service running `ceia-aisdk serve`; operator enabling `--token`.

- **User Stories**:

  **US-06-1 — Start the server**
  - As a developer, I want to run `ceia-aisdk serve` so that any OpenAI client can communicate with the SDK.
  - **Acceptance Criteria**:
    - The `[server]` extra installs FastAPI + uvicorn. Without the extra, the command explains how to install it.
    - Flags: `--host` (default 127.0.0.1), `--port` (11434), `--token`, `--cors`.
    - The ready log contains an absolute URL.

  **US-06-2 — Chat completions + models**
  - As a developer, I want to use `/v1/chat/completions` and `/v1/models` so that I can replace an OpenAI endpoint.
  - **Acceptance Criteria**:
    - Minimum fields: `model`, `messages`, `stream`, `temperature`, `max_tokens`.
    - `model` is an opaque alias (`llm/small`, etc.).
    - No conversation persistence on the server; each request is stateless apart from the model pool.

  **US-06-3 — Routes for other modules (adaptive)**
  - As a developer, I want embeddings and audio if PRDs 03/05 exist so that the server can grow without rework.
  - **Acceptance Criteria**:
    - If PRD 05 is merged: `/v1/embeddings`.
    - If PRD 03 is merged: `/v1/audio/transcriptions`, `/v1/audio/speech`.
    - Vision: if the client sends image_url/base64 in chat and PRD 04 exists, the server forwards it; otherwise, return a clear 400.
    - Tools in the OpenAI schema only if P1 of PRD 02 is complete; otherwise, return 400 “tools not available”.

  **US-06-4 — Localhost security**
  - As an operator, I want the server not to bind to the LAN by default so that running `serve` does not expose the GPU over the network.
  - **Acceptance Criteria**:
    - Default 127.0.0.1. Default CORS allows only localhost origins.
    - Explicit `--cors` to relax the restriction.
    - Token: header `Authorization: Bearer`.

- **Non-Goals**:
  - 100% compatibility with every obscure OpenAI API field (assistants, batches, files, fine-tune).
  - Multi-user auth, native TLS (reverse proxy is documented).
  - Custom web UI.
  - App launcher (PRD 07).
  - Redistributing the SDK as a binary; the `[server]` extra is only a pip dependency.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**: FastAPI, uvicorn, modules already delivered. Pool of LLM instances (and others) with a queue.
- **Evaluation Strategy**:
  - `TestClient`/httpx test: models, chat, SSE stream, 401.
  - Backpressure test: N parallel requests > pool size → 429 or wait with a documented timeout (choose **429 after the maximum queue size**, value in the spec, e.g., queue=8).
  - OpenAI contract: validate the JSON schema of happy-path responses.

---

### 4. Technical Specifications

- **Architecture Overview**:
  - `ceia_aisdk/server/openai_compat.py` + `serve` entry point.
  - Pool: 1 default instance of the requested alias; not thread-safe per instance (already established in 02) — the server serializes or isolates.
- **Integration Points**:
  - Port 11434 intentionally (drop-in vs Ollama). Conflict if Ollama is running → bind error with remediation guidance: “change `--port` or stop Ollama”.
  - The `[server]` extra is declared in this PRD (not in 00).
- **Security & Privacy**:
  - Localhost + optional token + restrictive CORS.
  - Do not log `messages` at INFO. DEBUG may do so when enabled by a flag.
  - Stateless: do not write history to disk.

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **P0**: serve + `/v1/models` + `/v1/chat/completions` (streaming and non-streaming) + auth/CORS + `[server]` extra on PyPI.
  - **P1**: embeddings/audio/vision/tools according to the modules available.
- **Technical Risks**:
  - Collision with Ollama on 11434 — desirable for compatibility, problematic for “both at the same time.” Mitigation: bind error message.
  - “OpenAI-compatible” tool calling is where clients break. Mitigation: explicit P1; do not advertise tools in `/v1/models` until support exists.

**Challenge:** Do not delay the server until voice/vision/RAG/OpenClaw. Library + serve is the second public demo, not the launcher.

**Speckit:** `openai-server` feature.
