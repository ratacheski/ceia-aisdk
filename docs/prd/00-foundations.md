# PRD 00 — Foundations

| Field | Value |
|---|---|
| ID | `PRD-00` |
| Status | Draft |
| Speckit slug | `sdk-foundations` |
| Depends on | — |
| Unblocks | PRD 01+ |
| PyPI | **Not published.** Installation from the repository only (`pip install -e .`). |
| Source plan | Stage 1 (with scope cuts) |

---

### 1. Executive Summary

- **Problem Statement**: Without an installable package, predictable configuration, hardware detection, and a diagnostic command, every inference module begins without an operational contract — and the team cannot open an issue or measure the 15-minute KPI.
- **Proposed Solution**: Deliver the `ceia-aisdk` skeleton in the repository: Python package, `ceia-aisdk` CLI, layered `AISDKConfig`, `hardware.py` with CPU/CUDA detection, an error hierarchy with `.remediation`, namespaced logging, and `ceia-aisdk doctor`. It is **not** uploaded to PyPI yet.
- **Success Criteria**:
  - `pip install -e .` (or a **local** wheel) installs the package in ≤ 60 s on a machine where Python 3.11+ is already present; the library wheel/sdist **without** extras is ≤ 5 MB beyond the declared foundation dependencies. There is no `twine upload` in this PRD.
  - `import ceia_aisdk` returns in ≤ 200 ms on an SSD and **does not** import `llama_cpp`, `faster_whisper`, `piper`, or `torch`.
  - `ceia-aisdk doctor` completes in ≤ 5 s and exits with code 0 on CPU-only Linux without a GPU; when NVIDIA is present, it reports the GPU name, total VRAM, and free VRAM with an error of ≤ 256 MB compared with `nvidia-smi`.
  - 100% of configuration precedence unit tests (kwargs > env > TOML > default) pass in Linux x86_64 CI.
  - Zero network calls during import and `doctor` (except local reads from sysfs/`nvidia-smi`).

---

### 2. User Experience & Functionality

- **User Personas**:
  - Hobbyist developer who has just cloned the repository and wants to know whether the machine is suitable.
  - Developer embedding the SDK in a Python script or service who needs to set `cache_dir` and `device`.
  - Maintainer receiving an issue: the `doctor` output is the required attachment.

- **User Stories**:

  **US-00-1 — Install the SDK from the repository**
  - As a developer, I want to run `pip install -e .` so that the product identifier exists in the local environment.
  - **Acceptance Criteria**:
    - `pyproject.toml` declares the name `ceia-aisdk`, importable package `ceia_aisdk`, console script `ceia-aisdk`, `requires-python = ">=3.11,<3.14"`, and classifier `Operating System :: POSIX :: Linux`.
    - The `[cuda]` extra exists as a documented stub (it may be empty or contain only a marker); extras `[server]` and `[apps]` are **not** required in this PRD.
    - `ceia-aisdk --help` lists at least `doctor`.
    - The version is available through `ceia_aisdk.__version__` and in `doctor` (it may be `0.0.0` / `0.1.0.dev0` until PRD 02 is published).
    - The README explicitly states: Linux x86_64, installation from the repository until 0.1.0.

  **US-00-2 — Configure in layers**
  - As a developer, I want to override the device and cache through kwargs, environment variables, or TOML so that the same code runs on a laptop and in CI.
  - **Acceptance Criteria**:
    - Precedence verified by tests: kwargs > `CEIA_AISDK_*` > `~/.ceia-aisdk/config.toml` > default.
    - Minimum environment variables in this PRD: `CEIA_AISDK_DEVICE`, `CEIA_AISDK_CACHE_DIR`, `CEIA_AISDK_LOG_LEVEL`, `CEIA_AISDK_OFFLINE`.
    - Default `cache_dir` = `~/.ceia-aisdk` (expanded); `device` = `auto`; `log_level` = `WARNING` in the logger (a TOML file may default to `INFO` if created, but the process starts at WARNING).
    - A missing TOML file is not an error; the SDK operates with defaults.
    - `CEIA_AISDK_OFFLINE=1` is read and persisted in `AISDKConfig.offline`; refusing downloads is implemented in PRD 01.

  **US-00-3 — Identify the hardware**
  - As a developer, I want the SDK to detect CUDA and fall back to CPU so that I do not have to configure the GPU manually.
  - **Acceptance Criteria**:
    - `get_device()` returns `cpu` | `cuda` | `cuda:N`.
    - Without an NVIDIA driver or GPU: `cpu`, without an exception, logging at DEBUG/INFO at most — **not** WARNING (this is not a failure).
    - With NVIDIA: identifies the index, name, total VRAM, and free VRAM.
    - If `device="cuda"` was forced and CUDA is unavailable: `DeviceError` with `.remediation` mentioning `device="cpu"` or installing the driver.
    - Fallback due to insufficient VRAM **waits for PRD 01/02** (it requires the model size). In this PRD, `get_device()` does not select an alias.

  **US-00-4 — Diagnose with doctor**
  - As a developer, I want a single diagnostic command so that I can open an issue with reproducible data.
  - **Acceptance Criteria**:
    - Prints: OS, architecture, Python, package version, selected device, GPUs, `cache_dir`, `offline`, installed extras, and a “copy this” block.
    - Exits with code 0 if the foundation is usable (supported Python + importable package).
    - Exits with code ≠ 0 if Python < 3.11 or if `device=cuda` was forced and failed.
    - Does not download models. Does not require internet access.

  **US-00-5 — Fail with remediation**
  - As a developer, I want errors to include a next action so that I do not have to read the native stack trace first.
  - **Acceptance Criteria**:
    - `AISDKError` is the root; this PRD includes `DeviceError` and, if useful internally, a `ConfigError`.
    - Every public instance exposes a non-empty `.remediation: str`.
    - `LicenseError` and `CatalogSignatureError` are **not** included in this PRD (see Non-Goals).

- **Non-Goals**:
  - Downloads, catalog, weight cache, and the `model *` CLI.
  - Any inference (LLM/STT/TTS/vision/RAG).
  - FastAPI, app launcher, and any desktop packaging (PyInstaller, Briefcase, binary).
  - Ed25519 signatures, mirrors, or telemetry sent to a server (the `CEIA_AISDK_TELEMETRY` flag may exist as a documented no-op).
  - `set_metrics_hook` may be deferred to PRD 02 — it is not required for `doctor`.
  - Apple Silicon, ROCm, Vulkan.
  - **Windows** (any edition): no CI, no `AppData` paths, no guarantee for `nvidia-smi`/console. Import may happen to work — that does not constitute support.
  - Upload to public PyPI (and announcement). Metadata in `pyproject.toml` is included; `twine`/`uv publish` are not. TestPyPI is optional and does not count as a launch.

---

### 3. AI System Requirements (If Applicable)

- **Tool Requirements**: no inference. Detection tools: `nvidia-smi` (subprocess, 2 s timeout), and/or CUDA bindings if already present. Do not add `torch` as a base installation dependency solely to detect a GPU.
- **Evaluation Strategy**:
  - Unit tests with mocked `nvidia-smi` (present, absent, timeout, VRAM).
  - Import test: an AST/hook ensures that `ceia_aisdk/__init__.py` does not import inference backends.
  - Linux x86_64 CI job: `pip install -e . && ceia-aisdk doctor`.
  - Optional self-hosted GPU job (TBD): `doctor` reports the runner GPU; if no runner is available, mark the *doctor* CUDA criterion as “tested on a reference machine” in the spec checklist — CUDA inference is a PRD 02 gate.

---

### 4. Technical Specifications

- **Architecture Overview**:
  - Package `ceia_aisdk/` with `__init__.py` (version + `AISDKConfig` / `get_device` if shortcut exports are desired), `config.py`, `hardware.py`, `errors.py`, and `cli.py`.
  - No `llm/`, `registry/`, or `server/` submodule is required in this increment. Empty directories must not be imported in `__init__`.
  - Flow: CLI/API → `AISDKConfig.load()` → `get_device(config)` → stdout/`doctor`.
- **Integration Points**:
  - Locked identifiers: PyPI/CLI `ceia-aisdk`, import `ceia_aisdk`, cache `~/.ceia-aisdk`, environment variables `CEIA_AISDK_*`, log namespace `ceia_aisdk.*`.
  - CLI: Typer + Rich (Rich only for `doctor` output; do not pull in the download stack).
  - Python: 3.11–3.13, Linux x86_64.
- **Security & Privacy**:
  - `doctor` does not send data to any endpoint.
  - Do not log the contents of user files.
  - Telemetry defaults to off. If the flag exists, it remains a no-op until a future PRD.

---

### 5. Risks & Roadmap

- **Phased Rollout**:
  - **This PRD**: package + config + hardware + errors + `doctor` + Linux CI. No public index.
  - **Publish**: PRD 02 (`0.1.0`). This PRD only prepares `pyproject.toml`.
  - **Outside this series**: signing, full documentation site, Windows.
- **Technical Risks**:
  - Detecting CUDA without `torch` depends on `nvidia-smi` being on PATH. Mitigation: two probes + 2 s timeout + mocked test. No Windows branch in this PRD.
  - An empty `[cuda]` extra in this PRD may frustrate early README readers. Mitigation: the foundation README states “inference in PRD 02.”
  - The Speckit Constitution is still a template — there is a risk of running specify without principles. Mitigation: ratify the constitution **before** this specify.

**Speckit:** feature description = this PRD. The acceptance criteria above become Scenario/AC entries in `spec.md`.
