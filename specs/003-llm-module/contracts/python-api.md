# Python API Contract: Local LLM Module

**Feature**: `003-llm-module`
**Stability**: Public contract for PRD-02, consumed by PRD-04+

This contract extends
[001-sdk-foundations/contracts/python-api.md](../../001-sdk-foundations/contracts/python-api.md)
and [002-model-registry/contracts/python-api.md](../../002-model-registry/contracts/python-api.md).

## Package Root

`ceia_aisdk.__init__` MUST NOT import `ceia_aisdk.llm` or `llama_cpp`. It MAY re-export
`GenerationError` and `CapabilityError` from `ceia_aisdk.errors` the same way it re-exports
registry errors.

`import ceia_aisdk` still finishes within the p95 200 ms reference target, makes no network
call, and MUST NOT leave `llama_cpp` in `sys.modules`.

## LLM Module

Public module: `ceia_aisdk.llm`.

`from ceia_aisdk.llm import LLM` MUST NOT import `llama_cpp`. The binding loads during
`LLM` / `AsyncLLM` construction after `ensure_local`, or on first generation, never earlier.

```python
class LLM:
    def __init__(
        self,
        alias: str | None = None,
        *,
        config: AISDKConfig | None = None,
        device: str | None = None,
        context_length: int | None = None,
        tools: Sequence[ToolDeclaration] | None = None,
    ) -> None: ...

    def chat(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> str: ...

    def stream(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> Iterator[str]: ...

    def session(self, system: str | None = None) -> Session: ...

    @property
    def alias(self) -> str: ...

    @property
    def device(self) -> str: ...
```

### Constructor

- `alias is None` uses `LLMSettings.default_alias` (`llm/small@latest` when no `[llm]` override).
- `LLM("medium")` is equivalent to `domain="llm"` plus size `medium`.
- `LLM("llm/medium")` and `LLM("llm/small@2")` are valid catalog forms.
- Explicit `alias` wins over `[llm] default_alias`.
- `config` defaults to `AISDKConfig.load()`.
- Explicit `device` overrides `config.device` for this instance.
- Calls `ensure_local` with a progress callback when stderr is a TTY.
- Offline cache miss raises `DownloadError` within 1 second without importing `llama_cpp`.
- Docstring MUST state the instance is not thread-safe.

### `chat`

- Returns a nonempty `str` for the smoke prompt `"Say only: ok"` on a working local model.
- Does not retain history on the `LLM` instance.
- Public failures are `AISDKError` subclasses.

### `stream`

- Yields an iterator of `str`.
- Under the same `seed` and `temperature=0`, concatenation equals `chat` when the backend is
  bit-stable; otherwise tests require ≥ 1 chunk and nonempty final text, and the limitation is
  documented.

### `session`

- Returns a `Session` bound to this instance.
- Two-turn memory is required at the API level (history is retained). Quality of coreference on
  a tiny CI GGUF is not a CI gate; it is a manual checklist on `llm/small`.

## Session

```python
class Session:
    def send(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> str: ...

    def stream(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> Iterator[str]: ...
```

Not thread-safe. Context overflow raises `GenerationError`.

## AsyncLLM

P1 included in this design. Same constructor arguments as `LLM`.

```python
class AsyncLLM:
    async def chat(...) -> str: ...
    def stream(...) -> AsyncIterator[str]: ...
    def session(self, system: str | None = None) -> AsyncSession: ...
```

Generation MAY use `asyncio.to_thread`. That limitation MUST be documented. At least one
asyncio smoke test with a timeout is required when this class ships in `0.1.0`.

## LLMSettings

```python
@dataclass(frozen=True, slots=True)
class LLMSettings:
    default_alias: str
    context_length: int

    @classmethod
    def load(
        cls,
        *,
        default_alias: str | None = None,
        context_length: int | None = None,
    ) -> LLMSettings: ...
```

See [configuration.md](configuration.md).

## Errors

Defined in `ceia_aisdk.errors`.

### `GenerationError`

Direct subclass of `AISDKError`. Raised for load or generate failures that are not device
selection or download/cache failures (including context overflow).

### `CapabilityError`

Direct subclass of `AISDKError`. Raised when tools are passed to an alias whose public
`capabilities` do not include `tool_use`.

Existing `DeviceError` remediation for GPU OOM MUST mention `llm/small` or `device="cpu"`.

## Tools

See [tools.md](tools.md). The `tools` constructor argument MAY be accepted in `0.1.0` or the
first patch. First-chat MUST NOT depend on it.

## Logging

- LLM modules use `logging.getLogger(__name__)`.
- CUDA generation logs a record whose message contains `cuda`.
- VRAM fallback logs `WARNING`.
- `WARNING` and `ERROR` records MUST NOT contain catalog URLs or prompt/completion bodies.
- No content telemetry.

## Documentation

Every public module, class, function, and method has an English docstring covering parameters,
returns, raised exceptions, and side effects (cache writes, backend load, not thread-safe).
