# PRD 02 — LLM Module

| Field | Value |
|---|---|
| ID | `PRD-02` |
| Status | Draft |
| Speckit Slug | `llm-module` |
| Depends on | PRD-00, PRD-01 |
| Unlocks | PRD 04, 05, 06; **first PyPI release** |
| PyPI | **`ceia-aisdk==0.1.0` — first public upload.** |
| Source Plan | Stage 3 |

---

### 1. Executive Summary

- **Problem Statement**: The public product only exists when a developer runs `from ceia_aisdk.llm import LLM` and receives a local response. Without this, the foundations and registry are invisible infrastructure.
- **Proposed Solution**: A `ceia_aisdk.llm` module built on `llama-cpp-python`, with `LLM` / `AsyncLLM`, chat, stream, session, automatic device selection (CPU + CUDA), aliases `llm/small|medium|large@N`, and **publication of package version 0.1.0 on PyPI**.
- **Success Criteria**:
  - On a clean Linux x86_64 system with a CPU and working network: from `pip install ceia-aisdk` **from public PyPI** (with the llama-cpp CPU runtime included or pulled as a dependency) to the first string returned by `LLM().chat("Say only: ok")` in **≤ 15 minutes**, including the `llm/small` pull.
  - `ceia-aisdk==0.1.0` is available on the index; classifiers declare Linux support; the PyPI page shows the quickstart and “Linux x86_64 only”.
  - The same call with `ceia-aisdk[cuda]` on an NVIDIA GPU with VRAM ≥ the requirement of `llm/small` completes on the `cuda` device (the log contains `cuda`); if VRAM is insufficient, it falls back to CPU with a WARNING and still returns a string.
  - For `LLM().chat` and the first token from `LLM().stream` with `llm/small` on CPU: first token ≤ 10 s once the model is already resident in RAM (warm).
  - Importing `ceia_aisdk` still does not load `llama_cpp`; only `from ceia_aisdk.llm import LLM` (or the first call) loads the backend.
  - Test matrix: chat, stream, session (2 turns with memory), forced `cpu` device, and at least 1 `AsyncLLM` test covering the same behavior.

---

### 2. User Experience & Functionality

- **User Personas**: a hobbyist who discovered the package on PyPI; a script that pins `llm/small@2` and `device="cpu"`; a CUDA user who expects it to “just work”.

- **User Stories**:

  **US-02-1 — First chat zero-config**
  - As a developer, I want to instantiate `LLM()` and call `.chat` so that I can validate the SDK in minutes.
  - **Acceptance Criteria**:
    - **Launch default: `llm/small@latest`**, not `medium`. Challenge to the plan: 4.3 GB breaks the 15-minute KPI on a typical home internet connection.
    - `config.toml [llm] default_alias = "medium"` and `LLM("medium")` remain valid.
    - `.chat` returns a non-empty `str` for the smoke prompt.
    - First use triggers `ensure_local` (PRD 01) with a progress indicator on a TTY.
    - Offline + cache miss → `DownloadError`; there is no > 1 s hang while attempting network access when `offline`.

  **US-02-2 — Streaming and session**
  - As a developer, I want streaming and multi-turn interaction so that the SDK can support a real chat.
  - **Acceptance Criteria**:
    - `.stream(prompt)` is an iterator of `str`; concatenation == the content that `.chat` would produce under the same fixed seed/temperature in the test (or documented equivalence if the backend is not bit-stable—in that case, the test checks ≥ 1 chunk and non-empty final text).
    - `.session(system=...)` retains history; the second `.send` demonstrates awareness of the first (fixture with a short factual question).
    - Thread safety: the docstring and documentation state “not thread-safe”.

  **US-02-3 — Mirrored async API**
  - As a developer, I want `AsyncLLM` with `.chat` / `.stream` / sessions so that I can embed it in asyncio.
  - **Acceptance Criteria**:
    - Same semantics as the synchronous class.
    - Do not block the event loop in the token hot path beyond what the binding permits (document if `llama-cpp-python` requires an executor). Test: `asyncio` + timeout.

  **US-02-4 — Real CUDA support**
  - As a developer with NVIDIA hardware, I want to `pip install ceia-aisdk[cuda]` so that inference uses the GPU without requiring me to select llama.cpp flags.
  - **Acceptance Criteria**:
    - The `[cuda]` extra installs/builds the binding with CUDA (pin and instructions in the README; prebuilt wheel if the team can provide one—otherwise, compilation documentation of ≤ 20 lines).
    - `device="auto"` + working GPU → layers on the GPU; `doctor` after installing the extra shows CUDA binding = yes.
    - OOM → `DeviceError` with remediation guidance (`llm/small` or `device="cpu"`), or CPU fallback if generation has not started yet.
    - The 15-minute clock **does not** include CUDA compilation. CUDA is a quality gate, not part of the anchor KPI.

  **US-02-5 — Tool use (P1, not P0)**
  - As a developer, I want to pass tools to chat so that the server (PRD 06) can expose tools later.
  - **Acceptance Criteria**:
    - The tools API is aligned with the OpenAI-ish format (name, JSON schema, call → result).
    - At least 1 test with a tool stub (`get_weather`) in which either the curated catalog model *or* a fixture/recording demonstrates the loop. If the default alias is not reliable for tools, the test uses an `llm/medium` alias marked `capabilities: [tool_use]` and remains P1—it **does not block** the first-chat merge.
    - Aliases without `tool_use` raise a clear error if tools are passed.

  **US-02-6 — Publish 0.1.0 on PyPI**
  - As an external developer, I want to `pip install ceia-aisdk` without cloning the repository so that the product actually exists.
  - **Acceptance Criteria**:
    - Version `0.1.0` on the public index.
    - The `[cuda]` extra can be installed via `pip install ceia-aisdk[cuda]`.
    - The project page declares Linux x86_64 support; it does not promise Windows support.
    - Wheel/sdist **does not** include GGUF weights.

- **Non-Goals**:
  - Fine-tuning, embeddings (PRD 05), vision (PRD 04), HTTP server (PRD 06).
  - Multiple backends (vLLM, Ollama as a runtime).
  - Guaranteeing benchmark quality versus cloud GPT.
  - Default `medium` in `LLM()`.
  - Binary, installer, or weight bundle in the wheel.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**:
  - Runtime: `llama-cpp-python` (GGUF).
  - Registry: `ensure_local("llm/small|medium|large")`.
  - Hardware: `get_device()` + catalog `size_gb` for VRAM fallback.
- **Evaluation Strategy**:
  - Mandatory smoke test: fixed prompt, assertion on a substring or regex (`ok` / non-empty + max 64 tokens).
  - Session golden test: 2 turns, assertion of simple coreference.
  - Informal benchmark (not a gate): CPU versus CUDA tokens/s on the reference machine; record in `doctor` or the DEBUG log.
  - Tool use: P1 test with a capable model, or an explicit skip if the CI artifact is a stub.

---

### 4. Technical Specifications

- **Architecture Overview**:
  - `ceia_aisdk/llm/model.py` (`LLM`), `async_model.py` (`AsyncLLM`).
  - Constructor: resolve alias → `ensure_local` → instantiate the binding with the configured n_ctx (`[llm] context_length`, default 8192).
  - VRAM fallback: if `size_gb` > available * margin (document 0.9), effective device = cpu + WARNING.
- **Integration Points**:
  - Catalog with three curated LLM aliases (real artifacts or placeholders until the HF organization exists; CI uses a tiny GGUF fixture).
  - CLI: no mandatory new subcommand beyond those already provided by PRD 01; quickstart in the README.
- **Security & Privacy**:
  - Prompts do not leave the machine. No content telemetry.
  - Instance is not thread-safe—document the race-condition risk; do not “fix” it with a silent global lock.

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **P0 (0.1.0 gate)**: synchronous `LLM` chat/stream/session + default `small` + CPU + `[cuda]` extra on the reference machine + **PyPI upload** + index README.
  - **P1** (may ship in 0.1.0 or the first patch): `AsyncLLM` + tool use + VRAM fallback. Tool use **does not** block 0.1.0.
  - **Later**: default `medium` only if p95 pull+chat < 15 min on the target bandwidth (TBD Mbps). Minors 03–07 in the same PyPI project.
- **Technical Risks**:
  - The CUDA build of `llama-cpp-python` is the #1 onboarding failure. Mitigation: documented wheels; `doctor` distinguishes “GPU visible” from “binding without CUDA”.
  - The tiny CI GGUF does not prove quality. Mitigation: CI smoke test + manual checklist with a real alias.
  - Default `small` versus the plan (`medium`): intentional divergence; reverting it requires updating this PRD and the KPI.

**Speckit:** feature `llm-module`. The spec must separate P0/P1 in the acceptance criteria.
