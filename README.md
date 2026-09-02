# CEIA AI SDK

Linux x86_64 foundation for the CEIA AI SDK. This repository is the local
install source until the public `0.1.0` release in PRD-02. Do not expect a
package named `ceia-aisdk` on public PyPI from this feature.

The base extra `[cuda]` is reserved and empty. It does not install a CUDA
runtime or any inference backend.

## Scope

- Supported platform: Linux x86_64
- Supported Python: 3.11, 3.12, and 3.13
- Distribution name: `ceia-aisdk`
- Import name: `ceia_aisdk`
- Console script: `ceia-aisdk`
- Public publication: not in this feature (PRD-02)

## Contributor setup

Install `uv`, then synchronize the locked environment:

```bash
uv python install 3.13
uv sync --python 3.13 --locked --all-groups --all-extras
uv lock --check
```

All contributor commands in this repository run through `uv`.

## Local installation

Editable install from a clone:

```bash
uv sync --locked --all-groups --all-extras
uv run python -c "import ceia_aisdk; print(ceia_aisdk.__version__)"
uv run ceia-aisdk --help
```

Build and install a local wheel without publishing:

```bash
uv build --no-sources
uv run --isolated --no-project --with dist/*.whl ceia-aisdk --help
```

Do not run `uv publish`. Public PyPI upload is reserved for PRD-02.

## CLI discovery

```bash
uv run ceia-aisdk --help
uv run ceia-aisdk doctor --help
uv run ceia-aisdk doctor
CEIA_AISDK_DEVICE=cpu uv run ceia-aisdk doctor
```

`ceia-aisdk doctor` inspects the local foundation. It does not download
models, create caches, or send telemetry.

## Configuration

`AISDKConfig` is an immutable snapshot. Each field is resolved independently
in this order: explicit arguments, `CEIA_AISDK_*` environment variables,
`~/.ceia-aisdk/config.toml`, then defaults.

Defaults:

- `device`: `auto`
- `cache_dir`: expanded `~/.ceia-aisdk` (the directory is not created)
- `log_level`: `WARNING` (case-sensitive; not trimmed)
- `offline`: `false` (`CEIA_AISDK_OFFLINE` accepts only `0` or `1`)

Example TOML:

```toml
[core]
device = "auto"
cache_dir = "~/.ceia-aisdk"
log_level = "WARNING"
offline = false
```

Environment override:

```bash
CEIA_AISDK_DEVICE=cpu \
CEIA_AISDK_CACHE_DIR=/tmp/ceia-cache \
CEIA_AISDK_LOG_LEVEL=INFO \
CEIA_AISDK_OFFLINE=1 \
uv run python -c "from ceia_aisdk import AISDKConfig; print(AISDKConfig.load())"
```

Explicit arguments win over the environment:

```python
from ceia_aisdk import AISDKConfig

config = AISDKConfig.load(device="cpu")
```

Mixed sources are valid: one field may come from an argument, another from
the environment, another from TOML, and another from a default. Invalid
lower-priority values are ignored when a valid higher-priority value exists.
A missing or empty TOML file is not an error. Malformed files and invalid
winning values raise `ConfigError` without echoing file contents.

## Hardware selection

`get_device()` returns `cpu` or `cuda:N`. Memory values are MiB. Automatic
selection uses the lowest usable NVIDIA index. Compute-prohibited GPUs and
enabled MIG devices are reported by `detect_gpus()` but are not selected.
This is not a guarantee that a future inference backend was built with CUDA.

```python
from ceia_aisdk import detect_gpus, get_device

get_device("cpu")  # never probes NVIDIA
get_device("auto")  # cuda:N or cpu
get_device("cuda")  # lowest usable index, or DeviceError
get_device("cuda:0")  # that index, or DeviceError
detect_gpus()  # ((index, name, total MiB, free MiB), ...)
```

## Troubleshooting

Invalid configuration raises `ConfigError` with a next action. The message
names the field and source when that is safe, and never prints the TOML file
or secret values:

```bash
CEIA_AISDK_DEVICE=nope uv run python -c "from ceia_aisdk import AISDKConfig; AISDKConfig.load()"
```

Forced CUDA without a usable GPU raises `DeviceError`. Use CPU or fix the
local driver/`nvidia-smi`/index:

```python
from ceia_aisdk import get_device

try:
    get_device("cuda")
except Exception as exc:  # DeviceError
    print(exc.remediation)
```

```bash
CEIA_AISDK_DEVICE=cuda uv run ceia-aisdk doctor
```

Automatic selection with no GPU is not an error: `get_device("auto")` returns
`cpu`.


