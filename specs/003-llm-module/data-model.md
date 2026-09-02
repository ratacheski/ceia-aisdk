# Data Model: Local LLM Module

**Feature**: `003-llm-module`
**Date**: 2026-09-02

This feature has no database. Persistent state remains the registry model cache. In-memory
objects are immutable after validation except session history, which is an ordered message list
owned by one `Session`.

## 1. LLM Settings

### Purpose

Launch defaults for alias and context window without changing the four-field `AISDKConfig`.

### Public representation

`LLMSettings` is an immutable, slotted value object.

### Fields

- `default_alias: str`
  - Canonical or size-only alias used when `LLM()` receives no alias.
  - Default: `llm/small@latest`.
- `context_length: int`
  - Positive generation context window. Default: `8192`.
  - Effective `n_ctx` is `min(context_length, PublicModelMetadata.context_length)`.

### Sources (each field independently)

1. Explicit constructor argument (`alias`, `context_length`).
2. `CEIA_AISDK_LLM_DEFAULT_ALIAS`, `CEIA_AISDK_LLM_CONTEXT_LENGTH`.
3. `~/.ceia-aisdk/config.toml` table `[llm]`.
4. Defaults above.

### Validation

- Alias, once normalized, must be acceptable to `resolve` (or fail later as
  `ModelNotFoundError`).
- `context_length` must be a positive integer.
- Invalid winning values raise `ConfigError` with nonempty remediation.

## 2. LLM Instance

### Purpose

A non-thread-safe local generator bound to one alias, one local file, and one effective device.

### Fields

- `alias: str`
  - Canonical `domain/size@N` after `resolve`.
- `path: Path`
  - Result of `ensure_local`.
- `effective_device: str`
  - `cpu` or `cuda:N`.
- `n_gpu_layers: int`
  - `0` on CPU, `-1` on CUDA.
- `n_ctx: int`
- `config: AISDKConfig`
- `settings: LLMSettings`
- `_backend: object | None`
  - Private loaded runtime; created on first generation or at end of `__init__` after
    `ensure_local`, never at `import ceia_aisdk` or `from ceia_aisdk.llm import LLM`.

### Invariants

- Default constructed alias is `llm/small@latest` unless settings or arguments override.
- Unqualified sizes use `domain="llm"`.
- `.chat` does not append to any session history.
- Concurrent use from two threads is undefined; no global lock exists.
- Prompts and completions are not sent to any network endpoint by this object.

### Failures

- Unknown alias → `ModelNotFoundError`.
- Offline cache miss → `DownloadError` within 1 second.
- Explicit CUDA unavailable or post-start OOM → `DeviceError`.
- Backend generation failure (context overflow, internal runtime error) → `GenerationError`.

## 3. Async LLM Instance

### Purpose

Mirror of `LLM` for asyncio callers.

### Fields

Same observable identity as `LLM`. Generation runs in a worker thread (`asyncio.to_thread` or
equivalent) because the binding is blocking.

### Invariants

Same alias default, obtain, session, and error types as `LLM`.

## 4. Generation Session

### Purpose

Retain system text and prior turns so a later send can depend on earlier content.

### Fields

- `system: str | None`
- `messages: list[ChatMessage]`
  - Ordered; starts empty aside from an optional system message.
- `owner: LLM | AsyncLLM`
  - The instance that performs generation. Not thread-safe.

### Transitions

```text
session(system?)
  -> send(user) / stream(user)
  -> append user
  -> generate
  -> append assistant
  -> return text or chunks
```

Context overflow raises `GenerationError` with remediation to shorten history or raise
`context_length`. No silent hang.

## 5. Chat Message

### Fields

- `role: Literal["system", "user", "assistant", "tool"]`
- `content: str`
- `name: str | None` (tool messages)
- `tool_call_id: str | None`

P0 uses `system`, `user`, and `assistant` only. `tool` appears when tool use ships.

## 6. Effective Device Decision

### Purpose

Map configured device, hardware snapshot, CUDA binding presence, and optional VRAM margin onto
`cpu` or `cuda:N`.

### Inputs

- Requested device from `AISDKConfig` or constructor override.
- `HardwareSnapshot` / `get_device` result.
- CUDA binding present (`true`/`false`).
- Catalog `size_gb`.
- Selected GPU `free_vram_mib`.
- Margin `0.9` (P1, included in this design).

### Rules

```text
requested cpu
  -> cpu (n_gpu_layers = 0)

requested auto
  -> no usable GPU or no CUDA binding -> cpu
  -> size_gb > 0.9 * (free_mib / 1024) -> cpu + WARNING
  -> else cuda:N (n_gpu_layers = -1), log contains "cuda"

requested cuda / cuda:N
  -> missing GPU or missing binding -> DeviceError
  -> size does not fit -> DeviceError (no silent CPU fallback)
  -> else cuda:N
```

Post-start GPU OOM → `DeviceError` mentioning `llm/small` or `device="cpu"`.

## 7. CUDA Extra and Binding Status

### Purpose

Tell operators whether the GPU-capable runtime is actually installed, independent of NVIDIA
visibility.

### Fields

- `extra_declared: bool`
  - Whether the `[cuda]` optional group is part of the installed distribution metadata.
- `binding_present: bool`
  - Whether `llama_cpp` imports and reports GPU offload support.

Doctor displays `cuda_binding=yes|no`. Missing extra on a CPU-only machine is not a failure.

## 8. Tool Declaration (P1, non-blocking)

### Fields

- `name: str`
  - Nonempty, unique in the tool list.
- `description: str`
- `parameters: Mapping[str, object]`
  - JSON Schema object.
- `handler: Callable[..., object] | None`
  - Optional local function for the call → result loop.

Accepted only when `PublicModelMetadata.capabilities` contains `tool_use`. Otherwise
`CapabilityError`.

## 9. Public LLM Errors

### Hierarchy

- `AISDKError` (existing)
  - `ConfigError` (existing) — invalid `[llm]` values
  - `DeviceError` (existing) — explicit CUDA / OOM
  - `ModelNotFoundError` (existing)
  - `DownloadError` (existing)
  - `GenerationError` (new) — load/generate failures that are not device or download
  - `CapabilityError` (new) — tools passed to an alias without `tool_use`

All expose nonempty English `.remediation`. `str(error)` contains no catalog URL or upstream
filename.

## State Transitions

### First chat

```text
LLM(alias?)
  -> load AISDKConfig + LLMSettings
  -> resolve alias (domain=llm for unqualified)
  -> ensure_local (progress on TTY)
  -> decide effective device
  -> lazy-import llama_cpp
  -> construct binding
  -> chat(prompt) -> nonempty str
```

### Offline miss

```text
offline and no valid cache
  -> DownloadError within 1 s
  -> llama_cpp not imported
```

### Stream

```text
stream(prompt)
  -> same completion path as chat
  -> yield str chunks
  -> concatenation equals chat when seed/temperature make the backend stable
```
