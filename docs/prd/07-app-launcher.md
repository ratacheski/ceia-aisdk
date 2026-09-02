# PRD 07 — App Launcher

| Field | Value |
|---|---|
| ID | `PRD-07` |
| Status | Draft |
| Speckit slug | `app-launcher` |
| Depends on | PRD-06 |
| Unblocks | “end user” persona (UI), without changing the SDK distribution channel |
| PyPI | Next minor release + `[apps]` extra. The SDK remains pip-only; apps are not included in the wheel. |
| Source plan | Stage 8 |

---

### 1. Executive Summary

- **Problem Statement**: End users do not `import` the SDK. Without an “install the chat and open the browser” path, the plan's third layer does not exist—but it is **not** what makes PyPI win over Ollama.
- **Proposed Solution**: `ceia-aisdk[apps]` extra, app catalog, and `ceia-aisdk app *` CLI. P0: Open WebUI via Docker pointing to the local server. P1: OpenClaw via npm with the `ceia` provider.
- **Success Criteria**:
  - `ceia-aisdk app install openwebui` + `app run openwebui` starts WebUI, and an HTTP GET to the UI (on the documented port) returns 200 in ≤ 3 min when Docker is already installed and `serve` is running.
  - The saved configuration points `OPENAI_API_BASE_URL` (or equivalent) to `http://127.0.0.1:11434/v1` without requiring the user to edit a file.
  - `app stop` / `uninstall` terminate the container/process and remove SDK-managed state; `status` reflects running/stopped.
  - Without Docker, `install openwebui` fails in ≤ 2 s with remediation guidance (“install Docker Engine”).
  - OpenClaw: P1 criteria—`install` + `baseUrl` configuration in `openclaw.json`; does not block the P0 merge.

---

### 2. User Experience & Functionality

- **User Personas**: end user guided by a README; hobbyist who wants a UI; the plan identifies OpenClaw as an agent.

- **User Stories**:

  **US-07-1 — List and install Open WebUI (P0)**
  - As a user, I want to `app install openwebui` so that I have browser-based chat connected to the SDK.
  - **Acceptance Criteria**:
    - `app list` shows `openwebui` (P0) and `openclaw` (visible and marked if P1 is incomplete).
    - Method: Docker. The image is pinned by digest or immutable tag in the registry YAML.
    - `run` opens/prints the localhost URL. `stop`, `status`, and `uninstall` are implemented.
    - Does this PRD automatically start `serve`? **Decision: `app run` checks the server; if it is down, it attempts to start `serve` in the background or fails with remediation guidance.** Prefer an **explicit failure** (“run `ceia-aisdk serve`”) in P0 to avoid hiding two processes. Joint supervision = P1.

  **US-07-2 — Install OpenClaw (P1)**
  - As a developer, I want to `app install openclaw` so that the agent uses the local provider.
  - **Acceptance Criteria**:
    - Method: npm with a pinned `openclaw@` version.
    - Writes the `ceia` provider with `baseUrl http://127.0.0.1:11434/v1`, `api: openai-completions`, and an `apiKey` placeholder or the `serve` token.
    - Without Node/npm → error with remediation guidance.
    - We do not claim compatibility with every channel (WhatsApp, etc.)—only Control UI / local chat.

- **Non-Goals**:
  - Generic app store for any OSS.
  - Package Open WebUI without Docker in this PRD (WebUI's pip path is fragile).
  - Distribute the SDK or UIs as a binary/installer. The user installs `ceia-aisdk[apps]` from PyPI; the runner downloads the UI (Docker/npm) to the machine.
  - Continue, Aider, Open Interpreter.
  - Automatic app updater.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**: Docker Engine (P0), Node/npm (P1), and the PRD 06 server. No new inference.
- **Evaluation Strategy**:
  - CI: runner tests with a mocked/fake Docker implementation (do not pull the image in unit tests).
  - Manual/nightly job: real WebUI installation (runner TBD).
  - Snapshot of the generated JSON/env (assert `11434` and `/v1`).

---

### 4. Technical Specifications

- **Architecture Overview**:
  - `ceia_aisdk/apps/{registry,runner}.py` + app YAML.
  - Installation methods: `docker` | `npm` (| `pip` / `git` in the schema, not required for P0).
- **Integration Points**:
  - `[apps]` extra.
  - Contract with PRD 06: host/port/token.
- **Security & Privacy**:
  - Do not expose app ports on `0.0.0.0` without an explicit flag.
  - Do not commit tokens to the example YAML.
  - OpenClaw has a history of broad network exposure—our runner defaults to localhost only / no external channels until the user configures them.

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **P0**: Open WebUI + `app *` CLI + extra.
  - **P1**: OpenClaw + auto-serve.
  - **v2**: more apps if the registry proves valuable.
- **Technical Risks**:
  - Docker + npm as product dependencies impose a greater support burden than the entire SDK. Therefore, P0 is Docker/WebUI only.
  - OpenClaw changes quickly (2026.x releases). Strict version pinning + `app uninstall`.
  - Work on this PRD must **not** begin before 06 is green—otherwise, the team will be debugging a third-party frontend.

**Challenge to the plan:** including the launcher in the “mandatory v1” alongside OpenClaw is vanity until `serve` is drop-in. It remains in the series because discovery did not remove it; it has been sequenced and divided into phases.

**Speckit:** feature `app-launcher`. The spec must mark OpenClaw as P1.
