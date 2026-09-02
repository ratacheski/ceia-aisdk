# Design: Local AI SDK for x86 PCs

**Date:** 2026-07-29
**Updated:** 2026-09-01
**Status:** Design validated — ready for implementation planning
**Official name:** `ceia-aisdk`

| Surface | Identifier |
|---|---|
| Product | CEIA AI SDK |
| PyPI / CLI | `ceia-aisdk` |
| Python import | `ceia_aisdk` |
| Cache and config | `~/.ceia-aisdk/` |
| Env vars | `CEIA_AISDK_*` |
| Logging | `ceia_aisdk.*` |
| HuggingFace org | `ceia-aisdk` |

Internal classes (`AISDKConfig`, `AISDKError`, and subclasses) retain the short `AISDK` prefix — the acronym still describes the product.

---

## TL;DR

Python SDK for x86 PCs (Windows/Linux) that delivers local multimodal AI capabilities — LLM, STT, TTS, computer vision, and RAG — with a modular API organized by domain, smart defaults, and escape hatches for customization. Distributed via `pip` as `ceia-aisdk`, with an opaque, versioned model registry (Ed25519-signed catalog, weights in a HuggingFace org with mirrors and the same `sha256`), an OpenAI-compatible server mode, and an app launcher that installs Open WebUI and OpenClaw configured to use the local server. Backends selected for maturity: `llama-cpp-python`, `faster-whisper`, `piper-tts`, `sentence-transformers`, `lancedb`. Target hardware: CPU + automatic NVIDIA CUDA detection. Models are loaded lazily on first use of each module; `ceia-aisdk model pull --essentials` prepares the minimum offline set.

---

## 1. Vision and guiding principles

### Vision

A Python SDK for x86 PCs (Windows/Linux) that delivers local multimodal AI capabilities (LLM, STT, TTS, vision, RAG) with a modular API, zero-config defaults, and escape hatches for users who need customization.

### Target personas

- **Hobbyist developer / prototyper** — wants 3 lines of code that "just works." Typical flow: `pip install ceia-aisdk` → `from ceia_aisdk.llm import LLM` → start chatting.
- **Product developer** — wants to embed it in a desktop app (via PyInstaller/Briefcase). Needs control over the model, cache path, logging, and reliable distribution.
- **End user** — never sees the SDK directly. Uses reference apps that bundle the SDK and hide all implementation details.

### Three product layers

1. **Python library** (`import ceia_aisdk`) — for developers to use in code.
2. **Server mode** (`ceia-aisdk serve`) — exposes an OpenAI-compatible HTTP API, allowing any ecosystem client (LangChain, LibreChat, Continue, etc.) to use the SDK as a local backend.
3. **App launcher** (`ceia-aisdk app install <name>`) — installs preconfigured OSS frontends connected to the local server. Delivers a "ready-to-use product" for end users in minutes. v1 reference apps: **Open WebUI** (chat) and **OpenClaw** (agent).

### Five design principles

1. **Smart defaults over configuration.** Every public function works without arguments.
2. **Modular API by domain.** `ceia_aisdk.llm`, `ceia_aisdk.stt`, `ceia_aisdk.tts`, `ceia_aisdk.vision`, `ceia_aisdk.rag` — each is self-contained; importing one does not load the others.
3. **Sync-first, async-parallel.** Every public method has mirrored sync (`.chat`) and async (`.achat`) versions, like `openai` and `httpx`.
4. **Transparent hardware.** Automatically detects CUDA at initialization and falls back to CPU without raising an alarm. Developers can force a device via `device="cpu"` or an env var.
5. **Models are versioned, opaque artifacts.** Stable aliases (`llm/small@N`), on-demand downloads with checksums, deterministic caching, and the actual underlying model is never exposed publicly.

### Non-goals

- Does not replace LangChain/LlamaIndex — it is not an agent framework.
- Does not target Apple Silicon as a primary platform (x86 first).
- Does not perform fine-tuning — inference only.
- Does not host a server by default (although an optional server mode is available).

---

## 2. Architecture and modules

### Python package layout

```
ceia_aisdk/
├── __init__.py          # exports top-level helpers (version, config)
├── config.py            # AISDKConfig (paths, device, log level)
├── hardware.py          # detect_cuda(), get_device(), memory_info()
├── registry/            # model catalog + resolver + downloader
│   ├── catalog.py       # curated aliases (opaque) → internal files
│   ├── downloader.py    # HTTP + resume + progress bar + mirror failover
│   ├── signing.py       # Ed25519 catalog verification
│   └── cache.py         # ~/.ceia-aisdk/models/ layout, lockfiles
├── llm/                 # text + vision (via LLaVA/MiniCPM-V)
│   ├── model.py         # class LLM (sync)
│   └── async_model.py   # class AsyncLLM (asyncio)
├── stt/                 # faster-whisper wrapper
├── tts/                 # Piper wrapper
├── vision/              # shortcut for vision LLM + ONNX modules (OCR, detect)
├── rag/                 # LanceDB + BGE-small + loaders (PDF/DOCX/MD/TXT)
├── server/              # FastAPI: OpenAI-compatible routes
│   └── openai_compat.py # /v1/chat/completions, /v1/embeddings, /v1/audio/*
├── apps/                # OSS app launcher
│   ├── registry.py      # app catalog (openwebui, openclaw)
│   └── runner.py        # install, configure, run, uninstall
└── cli.py               # `ceia-aisdk` command (Typer)
```

### Selected backends

| Domain | Backend | Format | Notes |
|---|---|---|---|
| LLM + vision | `llama-cpp-python` | GGUF | Supports chat + LLaVA/MiniCPM-V in the same runtime, with native CUDA + CPU support |
| STT | `faster-whisper` | CTranslate2 | ~4x faster than openai/whisper, with native CUDA support |
| TTS | `piper-tts` | ONNX | Lightweight, good quality, PT-BR available |
| Embeddings | `sentence-transformers` + `onnxruntime` | ONNX | BGE-small by default (~130MB), runs on CPU |
| Vector store | `lancedb` | local file | Zero setup, single file |
| Specialized vision (OCR/detect) | `onnxruntime` | ONNX | Optional YOLO and PaddleOCR |
| HTTP server | `FastAPI` + `uvicorn` | — | OpenAI-compatible routes |
| CLI | `Typer` + `Rich` | — | Modern UX |

### Optional dependencies (extras)

- `ceia-aisdk[cuda]` — forces a CUDA build of `llama-cpp-python`.
- `ceia-aisdk[server]` — includes FastAPI/uvicorn.
- `ceia-aisdk[apps]` — includes the app runner.

**Base installation:** `pip install ceia-aisdk` (~50 MB, SDK + bindings only). Models are pulled on demand.

---

## 3. Model registry and lifecycle

### Opaque, versioned aliases

Every curated alias includes a version (`@N`) that pins the artifact **immutably**. Once published, `llm/medium@3` always refers to the same file — it remains reproducible forever. The actual underlying model is **never** exposed through the public API.

```python
LLM()                    # default alias (llm/medium@latest for the SDK version)
LLM("small")             # unversioned alias → resolves to @latest for the installed version
LLM("small@2")           # explicit pinning, frozen against updates
LLM("hf://TheBloke/...") # full bypass (developer assumes responsibility)
LLM("/path/local.gguf")  # bring-your-own
```

### Update policy

Each alias's `@latest` is pinned by the installed SDK version. Upgrading from `ceia-aisdk 1.4` to `1.5` may change the model behind `llm/medium`, but it never changes within the same SDK version. This eliminates the "model silently updated overnight" problem.

### Internal catalog vs. public metadata

Internal file (`ceia_aisdk/registry/_internal_catalog.yaml`, not exposed through the public API):

```yaml
llm/medium@3:
  _internal:
    repo: <hidden>
    file: <hidden>
    sha256: <hidden>
    mirrors:
      - https://huggingface.co/ceia-aisdk/...
      - https://<mirror-2>/...
  public:
    license_family: apache-2.0
    commercial_use: true
    context_length: 32768
    size_gb: 4.3
    capabilities: [chat, tool_use, multilingual]
    quantization_class: standard
```

`ceia-aisdk model info llm/medium@3` returns **only the `public` section**. It never returns `_internal`. The `_internal_catalog` submodule uses a leading underscore to make it clear that it is "not an API."

### Exposed public metadata

- `license_family` (apache-2.0, mit, llama-community, gemma, custom, ...)
- `commercial_use` (bool)
- `context_length`
- `size_gb`
- `capabilities` (list: chat, tool_use, multilingual, vision, ...)
- `quantization_class` (compact, standard, high-quality)

Rationale: users deploying commercially need to know the license. Compliance remains the user's responsibility; the SDK exposes the minimum information required to make that decision.

### On-disk cache (opaque)

```
~/.ceia-aisdk/
├── models/
│   ├── llm/
│   │   └── medium-v3.bin      # opaque name, with no reference to the actual model
│   ├── stt/
│   └── ...
├── registry.lock              # snapshot of the catalog version
└── config.toml
```

Note: running `strings` on the GGUF file may still reveal metadata embedded by the original authors. This is acceptable — the goal is not to protect against a determined attacker, only to prevent developers from creating accidental dependencies.

### Hosting, mirrors, and failover

Primary source for curated weights: **HuggingFace organization `ceia-aisdk`**. HF provides resume support (range requests), a global CDN, and a workflow already familiar to companies and firewalls.

Each catalog artifact declares an ordered list of URLs with the **same `sha256`**:

1. HuggingFace (`huggingface.co/ceia-aisdk/...`) — primary.
2. One or more official mirrors (same object, same checksum). These may be another HF endpoint, object storage, or a CDN; the file identity is defined by its hash, not its host.
3. If all sources fail: `DownloadError` with `.remediation` pointing to `CEIA_AISDK_CATALOG` and offline mode.

Downloader failover policy:

- Tries the next mirror only after a network error, HTTP 5xx response, timeout, or invalid checksum.
- An invalid checksum is **not** ignored — the partial file is discarded and the next mirror is attempted.
- No BitTorrent: its complexity, UX, and legal exposure are disproportionate to the benefit.
- Enterprises / air-gapped environments: `CEIA_AISDK_CATALOG` points to a private catalog (HTTP or local path). The downloader honors the URLs in that catalog and does not try the public organization.

The catalog bundled in the wheel is the source of truth for the installed version. Remote catalog refresh is opt-in (`CEIA_AISDK_CATALOG=https://...`) and is accepted only if the Ed25519 signature is valid.

### Catalog signing and verification

The catalog is a trusted artifact: it specifies *what* to download and *which hash* to accept. Without a signature, a MITM targeting `CEIA_AISDK_CATALOG` (or a catalog mirror) could change both the URL and checksum.

- Algorithm: **Ed25519**.
- Public key embedded in the wheel (`ceia_aisdk/registry/keys/catalog.pub`). Rotation requires a new SDK version.
- Every published catalog includes `catalog.yaml` + `catalog.yaml.sig`.
- Bundled catalog: verified when the registry is first loaded (integrity is already reinforced by the wheel/PyPI).
- Remote catalog or path provided via `CEIA_AISDK_CATALOG`: **signature required**. Rejected with `CatalogSignatureError` if `.sig` is missing, the key does not match, or the payload differs.
- Escape hatch: `CEIA_AISDK_ALLOW_UNSIGNED_CATALOG=1` accepts an unsigned catalog and emits an explicit warning (air gap / lab). Default: off.
- `ceia-aisdk model verify` revalidates the signature of the active catalog **and** the `sha256` of each cached artifact.

### Download and integrity

- CLI: `ceia-aisdk model pull llm/small`, or lazy download on first API use.
- HTTP with resume (range requests), a Rich progress bar, mandatory checksum validation, and failover as described above.
- Mirrors and private catalog configured via `CEIA_AISDK_CATALOG`.

### Essentials bundle (not automatic)

`pip install ceia-aisdk` **does not** download models. On first use, each module pulls only the default alias for its domain (`LLM()` → `llm/medium`, `STT()` → `stt/fast`, etc.).

To prepare a minimum offline set (CI, demo, or a machine that will later have no network access):

```bash
ceia-aisdk model pull --essentials
```

Essentials bundle aliases (always the `@latest` versions pinned by the SDK version):

| Alias | Role | Approximate size |
|---|---|---|
| `llm/small` | viable CPU chat | ~1–2 GB |
| `stt/fast` | transcription | ~150 MB |
| `tts/pt-br` | PT-BR voice (bundle default; `tts/en-us` is included if `CEIA_AISDK_TTS_LOCALE=en-us`) | ~60 MB |
| `embed/default` | RAG / embeddings | ~130 MB |

`ceia-aisdk bundle create` remains the mechanism for *packagers* to choose an arbitrary manifest (not only essentials) and embed the weights in the app artifact.

### Management commands

- `ceia-aisdk model list`
- `ceia-aisdk model pull <alias>`
- `ceia-aisdk model pull --essentials`
- `ceia-aisdk model rm <alias>`
- `ceia-aisdk model info <alias>` — shows public metadata only
- `ceia-aisdk model verify` — rechecks the catalog signature + file integrity
- `ceia-aisdk model where <alias>` — prints the cache path

### Accepted trade-off

Developers who need in-depth debugging will use explicit `hf://` URLs or local models. That is the cost of opacity — documented accordingly.

---

## 4. Concrete API by module

Mirrored sync/async APIs; zero-config by default; escape hatches available.

### LLM (text + tool use)

```python
from ceia_aisdk.llm import LLM

llm = LLM()                                     # llm/medium@latest, auto-device
resp = llm.chat("Explain RAG in one sentence")  # str

for chunk in llm.stream("Write a haiku"):        # str iterator
    print(chunk, end="", flush=True)

# Multi-turn session
chat = llm.session(system="You are concise.")
chat.send("Hi")
chat.send("Remind me what I asked before?")

# Mirrored async API
from ceia_aisdk.llm import AsyncLLM
llm = AsyncLLM()
resp = await llm.chat("...")
async for chunk in llm.stream("..."):
    ...
```

### STT (audio → text)

```python
from ceia_aisdk.stt import STT

stt = STT()                                          # stt/fast@latest
text = stt.transcribe("audio.wav")                   # str
result = stt.transcribe("audio.wav", timestamps=True)

# Microphone streaming
for partial in stt.stream_microphone():
    print(partial)
```

### TTS (text → audio)

```python
from ceia_aisdk.tts import TTS

tts = TTS(voice="pt-br")                             # tts/pt-br@latest
tts.speak("Hello, world").play()
tts.speak("Hello").save("out.wav")
```

### Vision (image + prompt)

```python
from ceia_aisdk.vision import Vision

v = Vision()                                         # vision/small@latest
answer = v.describe("photo.jpg", prompt="What is wrong with this configuration?")

# Specialized utilities (ONNX)
from ceia_aisdk.vision import ocr, detect
text = ocr("invoice.png")
boxes = detect("garage.jpg", classes=["car", "person"])
```

### RAG (zero-config)

```python
from ceia_aisdk.rag import RAG

kb = RAG("my-kb")                                    # ~/.ceia-aisdk/rag/my-kb
kb.add("./docs/")                                    # PDF, MD, DOCX, TXT, HTML
kb.add("https://example.com/page.html")
answer = kb.ask("How do I configure X?")             # answer + sources

# Escape hatch for retrieval only
chunks = kb.retrieve("How do I configure X?", top_k=5)
```

### OpenAI-compatible server (CLI)

```bash
ceia-aisdk serve --port 11434 --host 127.0.0.1
# Any OpenAI client can point base_url to localhost:11434
```

### App launcher (CLI)

v1 reference apps, both OSS and connected to `ceia-aisdk serve`:

| App | Role | Installation | Sources |
|---|---|---|---|
| `openwebui` | Multimodal chat in the browser | Docker (preferred) or pip | [Open WebUI](https://github.com/open-webui/open-webui) |
| `openclaw` | Self-hosted agent (channels + Control UI + tools) | npm (`openclaw@latest`) | [openclaw/openclaw](https://github.com/openclaw/openclaw) · [docs](https://docs.openclaw.ai) · MIT |

OpenClaw (v2026.8.x / 2.0) accepts an OpenAI-compatible provider via `baseUrl`. The runner writes a local provider to `~/.openclaw/openclaw.json`:

```json5
{
  models: {
    mode: "merge",
    providers: {
      ceia: {
        baseUrl: "http://127.0.0.1:11434/v1",
        api: "openai-completions",
        apiKey: "ceia-local",
        models: [{ id: "llm/medium", name: "CEIA medium" }]
      }
    }
  },
  agents: { defaults: { model: { primary: "ceia/llm/medium" } } }
}
```

The system uses `openai-completions` (`/v1/chat/completions`), not Ollama's native dialect. Tool calling must work correctly on this route — it is part of the server mode contract.

```bash
ceia-aisdk app list                    # openwebui, openclaw
ceia-aisdk app install openwebui       # downloads and configures it to use the local server
ceia-aisdk app install openclaw
ceia-aisdk app run openwebui           # opens it in the browser
ceia-aisdk app stop openwebui
```

---

## 5. Cross-cutting concerns

### Layered configuration

Precedence from strongest to weakest:

1. Per-call kwargs: `LLM(device="cpu", cache_dir="/tmp")`
2. Env vars: `CEIA_AISDK_DEVICE`, `CEIA_AISDK_CACHE_DIR`, `CEIA_AISDK_LOG_LEVEL`, `CEIA_AISDK_CATALOG`, `CEIA_AISDK_OFFLINE`, `CEIA_AISDK_ALLOW_UNSIGNED_CATALOG`, `CEIA_AISDK_TTS_LOCALE`
3. Config file: `~/.ceia-aisdk/config.toml`
4. SDK defaults

```toml
# ~/.ceia-aisdk/config.toml
[core]
device = "auto"          # auto | cpu | cuda | cuda:0
cache_dir = "~/.ceia-aisdk"
log_level = "INFO"
offline = false          # if true, fail instead of attempting a download

[llm]
default_alias = "medium"
context_length = 8192

[server]
host = "127.0.0.1"       # NEVER 0.0.0.0 by default
port = 11434
require_token = false
```

### Hardware detection

On the first call to each module, `get_device()`:

- Attempts to import `torch.cuda` / check `nvidia-smi` and `cuda_runtime`.
- If available: checks free VRAM; if the requested model does not fit, falls back to CPU with a warning.
- Clear log message: `[ceia_aisdk.hardware] Using device: cuda:0 (RTX 3060, 12GB VRAM, 8.2GB free)`.
- The `ceia-aisdk doctor` CLI command prints full detection results, binding versions, drivers, and sanity checks. It becomes the command to run before opening an issue.

### Logging & observability

- Standard Python `logging`, under the `ceia_aisdk.*` namespace. Silent by default (`WARNING`).
- Optional metrics callback: `ceia_aisdk.set_metrics_hook(fn)` receives `{event, module, alias, duration_ms, tokens, ...}` events — developers can connect it to Prometheus/OpenTelemetry.
- **Out-of-the-box telemetry: zero.** Nothing is sent to an external server without explicit opt-in (`CEIA_AISDK_TELEMETRY=1`). Local-first means privacy-first.

### Error hierarchy

```
AISDKError                   # root
├── ModelNotFoundError       # nonexistent alias
├── DownloadError            # network, checksum, full disk, exhausted mirrors
├── CatalogSignatureError    # remote catalog without a valid signature
├── DeviceError              # CUDA OOM, driver mismatch
├── BackendError             # llama.cpp/whisper/etc. failure
└── LicenseError             # attempted commercial use of a non-commercial model
```

Each error has `.remediation` (a user-friendly string): `"CUDA OOM. Try a smaller alias like 'llm/small' or set device='cpu'."`

### Thread safety & concurrency

- `LLM/STT/TTS` instances are **not** thread-safe (shared native backend). Docstrings state this explicitly.
- True concurrency: `AsyncLLM` (asyncio) or a pool of instances.
- Server mode manages the pool internally — developers do not see it.

### Server mode security

- Binds to `127.0.0.1` by default (never `0.0.0.0`).
- `--token <secret>` enables Bearer auth.
- CORS is restricted by default (localhost); the `--cors <origins>` flag explicitly relaxes it.
- No conversation persistence on the server; stateless between requests.

### Packaging for end-user apps

- Guide + templates for PyInstaller and Briefcase.
- A packaged app inherits the SDK cache; it can include pre-downloaded "essential models" via `ceia-aisdk bundle create`.

---

## 6. Development stages

Ordered by technical dependency. Full scope — no MVP cuts or timelines.

### Stage 1 — Foundations

The foundation supporting everything else.

- Repository setup (`pyproject.toml` named `ceia-aisdk`, extras, Linux/Windows CI matrix).
- Layered config system (`AISDKConfig`, `CEIA_AISDK_*` env vars, TOML in `~/.ceia-aisdk/`).
- `hardware.py` module (CUDA detection, VRAM, device selection with fallback).
- Error hierarchy (`AISDKError` + subclasses with `.remediation`, including `CatalogSignatureError`).
- Namespaced logging (`ceia_aisdk.*`).
- Base CLI using `Typer`, the `ceia-aisdk` command, and the `ceia-aisdk doctor` subcommand.

### Stage 2 — Model registry and cache

Prerequisite for every inference module.

- Internal catalog schema (YAML) with versioned aliases (immutable `@N`) and a list of mirrors per artifact.
- Public metadata layer (opacity — only `license_family`, capabilities, size).
- Ed25519 signature (`catalog.yaml.sig`), public key in the wheel, rejection of unsigned remote catalogs (except through the escape hatch).
- Alias resolver (`llm/medium` → `llm/medium@N`).
- Downloader with resume, checksum validation, mirror failover, and a progress bar.
- Cache manager (`~/.ceia-aisdk/models/`, lockfiles, cleanup).
- CLI subcommands: `model pull/list/rm/info/verify/where` and `model pull --essentials`.

### Stage 3 — LLM module

First real backend; validates all previous infrastructure.

- `llama-cpp-python` integration with automatic device selection.
- Sync `LLM`: `.chat`, `.stream`, `.session`, tool use.
- Mirrored `AsyncLLM`.
- Curation of `llm/small|medium|large@N` aliases in the internal catalog.

### Stage 4 — Voice modules

Reuse the registry/cache from Stage 2.

- STT via `faster-whisper` (transcribe, timestamps, microphone stream) — sync + async.
- TTS via `piper-tts` (speak → play/save) — sync + async.
- Aliases `stt/fast|accurate@N`, `tts/pt-br|en-us@N`.

### Stage 5 — Vision module

Depends on the LLM backend from Stage 3.

- Multimodal support via `Vision().describe(image, prompt)`, reusing the Stage 3 runtime with LLaVA/MiniCPM-V.
- Independent ONNX utilities: `vision.ocr()`, `vision.detect()`.
- Aliases `vision/small@N`, `vision/ocr@N`, `vision/detect@N`.

### Stage 6 — RAG module

Depends on the LLM (for `.ask`); `.retrieve` is independent.

- Embeddings backend via `sentence-transformers` / ONNX (`embed/default@N`, `embed/multilingual@N` aliases).
- `lancedb` integration (named KB, local file).
- Loaders (PDF, DOCX, MD, TXT, HTML) + recursive chunking.
- `RAG.add / ask / retrieve / list / delete` API.

### Stage 7 — Server mode

Depends on the previous modules; exposes everything over HTTP.

- FastAPI + uvicorn as an optional extra (`ceia-aisdk[server]`).
- OpenAI-compatible routes: `/v1/chat/completions` (SSE stream + tool calling), `/v1/embeddings`, `/v1/audio/transcriptions`, `/v1/audio/speech`, `/v1/models` (returns opaque aliases only).
- Optional Bearer auth, restricted CORS, localhost binding by default.
- Internal instance pool with backpressure.

### Stage 8 — App launcher

Depends on server mode (Stage 7).

- App registry (YAML: installation method per app — docker / pip / npm / git+script).
- Runner: install, configure to use the local server, run, stop, status, uninstall.
- Bundled configs:
  - **Open WebUI** — Docker, `OPENAI_API_BASE_URL=http://127.0.0.1:11434/v1`.
  - **OpenClaw** — npm, `ceia` provider with local `baseUrl` and `api: openai-completions` (see §4).
- CLI subcommands: `app list/install/run/stop/status/uninstall`.

### Stage 9 — Packaging support

Independent of the later stages; can proceed in parallel.

- `ceia-aisdk bundle create` command (generates a manifest of pre-downloaded models).
- `ceia-aisdk model pull --essentials` as a shortcut for the minimum manifest.
- PyInstaller template.
- Briefcase template.
- Distribution guide for end-user apps.

### Stage 10 — Documentation and examples

Cross-cutting, but becomes more substantial after each stage above.

- API reference (mkdocs-material).
- Quickstarts by module.
- Cookbooks (voice assistant, chat with documents, screenshot analysis).
- Specialized docs: opacity, licensing, packaging, troubleshooting, catalog verification.

---

## Decision log

| # | Decision | Rejected alternatives |
|---|---|---|
| 1 | Target audience: developers and end users (via apps) | Developers only; researchers only |
| 2 | Language: Python with packaged reference apps | Rust/C++ with bindings; Node/TS; C#/Go |
| 3 | Scope: full multimodal support starting in v1 | Focus on LLM+RAG; focus on voice; focus on vision |
| 4 | Hardware: CPU + automatic NVIDIA CUDA detection | CPU only; multiple backends (ROCm/Vulkan); mini PC/edge |
| 5 | Model distribution: on-demand registry (Ollama style) | Bundled; hybrid; bring-your-own-model |
| 6 | API style: separate modules by domain | Functional; unified facade; multiple coexisting styles |
| 7 | RAG: zero-config | Layered config; composable components; LangChain wrapper |
| 8 | Concurrency: parallel sync + async (`chat`/`achat`) | Sync + optional streaming; streaming-first; async-first |
| 9 | Catalog: curated + custom by URL/path | Curated only; open HF-style catalog |
| 10 | Opacity: immutable versioned aliases (`@N`) | Fully opaque; opaque with a backdoor; opaque runtime + documentation reveals details |
| 11 | Public metadata: license family + capabilities only | Hide the license too; expose everything |
| 12 | Three-layer product: library + server + app launcher | Library only; library + a single app |
| 13 | Official name: `ceia-aisdk` (import `ceia_aisdk`) | `aisdk` (PyPI name occupied + generic); `aisdk-local` |
| 14 | Bundled apps: Open WebUI + OpenClaw | Continue; Aider; Open Interpreter; postpone the agent |
| 15 | Weights: HF org `ceia-aisdk` + catalog mirrors + `CEIA_AISDK_CATALOG` | HF only; first-party CDN as primary; torrent; self-hosted only in v1 |
| 16 | Ed25519-signed catalog; unsigned remote catalogs only through an escape hatch | Trust the wheel alone; postpone signing |
| 17 | No download during installation; lazy per module + `model pull --essentials` | Automatically download essentials on first import; no named bundle |

---

## Resolved questions (2026-09-01)

All open questions from the original design were resolved in this revision.

- **Final name.** Product/PyPI/CLI: `ceia-aisdk`. Import: `ceia_aisdk`. Cache: `~/.ceia-aisdk`. Env: `CEIA_AISDK_*`. `aisdk` on PyPI is occupied by a stub from 2021 and conceptually conflicts with Vercel's AI SDK.
- **OSS coding agent.** OpenClaw confirmed ([github.com/openclaw/openclaw](https://github.com/openclaw/openclaw), MIT, [docs.openclaw.ai](https://docs.openclaw.ai), v2026.8.x / 2.0). Accepts an OpenAI-compatible `baseUrl`; the launcher configures the `ceia` provider to use `ceia-aisdk serve`. Second app: Open WebUI.
- **Catalog mirrors.** HuggingFace org `ceia-aisdk` as primary; each artifact lists mirrors with the same `sha256`; automatic failover; `CEIA_AISDK_CATALOG` for air-gapped environments. No torrent.
- **Catalog signing.** Ed25519, public key in the wheel, `catalog.yaml.sig` required for remote catalogs. `CEIA_AISDK_ALLOW_UNSIGNED_CATALOG=1` is the escape hatch. `model verify` covers the signature + checksums. New error: `CatalogSignatureError`.
- **Essentials bundle.** No silent downloads during `pip install`. Lazy download on first use of each module. `ceia-aisdk model pull --essentials` downloads `llm/small`, `stt/fast`, `tts/pt-br` (or `tts/en-us` via locale), and `embed/default`.
