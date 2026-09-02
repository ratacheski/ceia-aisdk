# Python API Contract: Operational Foundations

**Feature**: `001-sdk-foundations`
**Stability**: Public contract for PRD-00

## Package Root

### `ceia_aisdk.__version__`

- Type: `str`
- Source: installed distribution metadata for `ceia-aisdk`
- Must equal the version in package metadata.
- Access must not import Typer, Rich, inference backends, or hardware drivers.

The package root may re-export the public foundation types and functions below, but it must not
import CLI or diagnostic-rendering modules.

## Configuration

### `AISDKConfig`

Immutable effective configuration with these public attributes:

- `device: str`
- `cache_dir: pathlib.Path`
- `log_level: str`
- `offline: bool`

Direct mutation is unsupported.

### `AISDKConfig.load`

```python
@classmethod
def load(
    cls,
    *,
    device: str | None = None,
    cache_dir: str | os.PathLike[str] | None = None,
    log_level: str | None = None,
    offline: bool | None = None,
) -> AISDKConfig:
    ...
```

Contract:

- A non-`None` argument is an explicit value and has highest precedence.
- `None` means that the explicit layer did not provide the field.
- Missing configuration files are accepted.
- The method returns a fully resolved, validated, immutable snapshot.
- Invalid selected values, malformed TOML, unreadable TOML, or unresolved home expansion raise
  `ConfigError`.
- Error messages must not reproduce the complete file, environment, or sensitive raw values.
- Loading configuration does not create directories, configure the root logger, probe hardware,
  or access the network.

See [configuration.md](configuration.md) for source and validation details.

## Hardware

### `GPUInfo`

Immutable public GPU value object:

```python
@dataclass(frozen=True, slots=True)
class GPUInfo:
    index: int
    name: str
    total_vram_mib: int
    free_vram_mib: int
```

Contract:

- Memory units are MiB.
- `index` is the local `nvidia-smi`/NVML index in PRD-00.
- Stable identifiers such as UUID, serial number, and PCI bus ID are not public fields.
- `0 <= free_vram_mib <= total_vram_mib`.

### `detect_gpus`

```python
def detect_gpus() -> tuple[GPUInfo, ...]:
    ...
```

Contract:

- Returns a tuple ordered by ascending GPU index.
- Returns an empty tuple when no NVIDIA GPU is available or when the bounded local probe cannot
  produce a trustworthy snapshot.
- Does not import `torch`, `llama_cpp`, `faster_whisper`, `piper`, or any inference backend.
- Does not access the network.
- Completes the local probe within the 2-second subprocess timeout.
- Probe failures may be logged at `DEBUG` or `INFO`, never `WARNING` or higher merely because no
  GPU is available.

### `get_device`

```python
def get_device(device: str = "auto") -> str:
    ...
```

Accepted input:

- `auto`
- `cpu`
- `cuda`
- `cuda:N`, where `N` is a canonical nonnegative integer

Return value:

- `cpu`
- `cuda:N`

Contract:

- `cpu` returns immediately without probing NVIDIA hardware.
- `auto` returns the lowest usable `cuda:N`, or `cpu` when no usable GPU is available or probing
  fails.
- `cuda` returns the lowest usable `cuda:N`; if unavailable, it raises `DeviceError`.
- `cuda:N` returns that exact index when usable; otherwise, it raises `DeviceError`.
- Invalid device syntax raises `DeviceError`.
- `DeviceError.remediation` must recommend `device="cpu"` or correction of the local CUDA
  driver/tool/index.
- Selection is independent of model aliases, model size, and future inference backends.

## Errors

### `AISDKError`

```python
class AISDKError(Exception):
    remediation: str

    def __init__(self, message: str, *, remediation: str) -> None:
        ...
```

Contract:

- `message` and `remediation` must both be nonempty English text.
- `.remediation` is always publicly available.
- String conversion includes the primary message without exposing private file contents.

### `ConfigError`

Direct subclass of `AISDKError` for invalid or unreadable effective configuration.

### `DeviceError`

Direct subclass of `AISDKError` for invalid or unavailable explicitly requested devices.

## Logging Contract

- Every package module obtains a logger through its full module name under `ceia_aisdk.*`.
- Importing the package installs at most a `NullHandler`.
- Importing or loading configuration must not call `logging.basicConfig`, add a stream handler,
  change the root level, or remove host-application handlers.
- CLI logging setup may set the `ceia_aisdk` namespace level from `AISDKConfig.log_level`.
- Repeated CLI logging setup must be idempotent.

## Import Contract

`import ceia_aisdk` must:

- finish within the p95 200 ms reference target;
- perform no network call or hardware subprocess;
- avoid importing Typer, Rich, and inference backends;
- expose a version consistent with distribution metadata;
- remain functional when optional groups are absent.

## Documentation Contract

Every public module, class, function, and every method has an English docstring. Docstrings
document parameters, returns, raised exceptions, and relevant side effects. The contract is
validated by static checks and public API tests.
