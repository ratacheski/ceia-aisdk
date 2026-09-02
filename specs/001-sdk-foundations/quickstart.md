# Quickstart Validation: CEIA AI SDK Operational Foundations

**Feature**: `001-sdk-foundations`

This guide validates the completed PRD-00 implementation. It is not an implementation guide and
does not replace the automated test suite.

## Prerequisites

- Linux x86_64
- `uv`
- Network access for initial dependency synchronization only
- Optional: an NVIDIA machine for the reference GPU check

The supported Python matrix is 3.11, 3.12, and 3.13. The examples below use Python 3.13.

## 1. Synchronize the Project

```bash
uv python install 3.13
uv sync --python 3.13 --locked --all-groups --all-extras
```

Expected outcome:

- synchronization succeeds from a clean checkout;
- `uv.lock` is accepted without modification;
- the project is installed in editable mode;
- no model or runtime cache is downloaded.

Verify lock consistency:

```bash
uv lock --check
```

## 2. Validate Package Import

```bash
uv run python -c "import ceia_aisdk; print(ceia_aisdk.__version__)"
```

Expected outcome:

- one nonempty version is printed;
- no hardware subprocess or network operation occurs;
- no inference backend is imported.

Run the import contract:

```bash
uv run pytest tests/contract/test_package_api.py tests/performance/test_import_timing.py
```

## 3. Validate CLI Discovery

```bash
uv run ceia-aisdk --help
uv run ceia-aisdk doctor --help
```

Expected outcome:

- both commands exit with code `0`;
- root help lists `doctor`;
- each help page describes its purpose and includes executable examples;
- all text is in English.

Run the help contract:

```bash
uv run pytest tests/contract/test_cli_help.py
```

## 4. Validate CPU-Only Diagnostics

Force the supported CPU path so the result is independent of installed NVIDIA hardware:

```bash
CEIA_AISDK_DEVICE=cpu uv run ceia-aisdk doctor
```

Expected outcome:

- exit code `0`;
- effective device `cpu`;
- all required environment and configuration fields;
- a complete `copy this` block;
- no model download, cache creation, network operation, or warning about the absence of a GPU.

Validate redirected plain output:

```bash
CEIA_AISDK_DEVICE=cpu uv run ceia-aisdk doctor > doctor.txt
uv run python -c "from pathlib import Path; assert '\x1b[' not in Path('doctor.txt').read_text()"
```

The generated `doctor.txt` is a temporary local validation artifact and must not be committed.

## 5. Validate Configuration Precedence

Create an isolated home directory and TOML file:

```bash
VALIDATION_HOME="$(mktemp -d)"
mkdir -p "$VALIDATION_HOME/.ceia-aisdk"
printf '%s\n' \
  '[core]' \
  'device = "cuda"' \
  'cache_dir = "~/from-toml"' \
  'log_level = "INFO"' \
  'offline = false' \
  > "$VALIDATION_HOME/.ceia-aisdk/config.toml"
```

Verify environment values override TOML:

```bash
HOME="$VALIDATION_HOME" \
CEIA_AISDK_DEVICE=cpu \
CEIA_AISDK_OFFLINE=1 \
uv run python -c \
  "from ceia_aisdk import AISDKConfig; c=AISDKConfig.load(); assert c.device == 'cpu' and c.offline is True"
```

Verify an explicit value overrides the environment:

```bash
HOME="$VALIDATION_HOME" \
CEIA_AISDK_DEVICE=cuda \
uv run python -c \
  "from ceia_aisdk import AISDKConfig; assert AISDKConfig.load(device='cpu').device == 'cpu'"
```

Run the full configuration matrix:

```bash
uv run pytest tests/unit/test_config.py
```

## 6. Validate Errors and Logging

```bash
uv run pytest \
  tests/contract/test_public_errors.py \
  tests/unit/test_logging.py
```

Expected outcome:

- every public error has nonempty remediation;
- invalid configuration and forced unavailable CUDA are actionable;
- package import does not alter root logger handlers or level;
- automatic CPU fallback does not emit `WARNING` or higher.

## 7. Validate Hardware Behavior

Run deterministic mocked hardware tests on any Linux x86_64 machine:

```bash
uv run pytest tests/unit/test_hardware.py tests/unit/test_diagnostics.py
```

Expected coverage includes:

- missing `nvidia-smi`;
- timeout;
- malformed and quoted CSV;
- single and multiple GPUs;
- prohibited compute and MIG;
- forced missing index;
- automatic CPU fallback.

On an optional NVIDIA reference machine:

```bash
uv run ceia-aisdk doctor
nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv,noheader,nounits
```

Compare readings taken close together. Names and indices must match, total memory must remain
stable, and free-memory difference must be at most 256 MiB.

## 8. Validate Privacy, Network Isolation, and Timing

```bash
uv run pytest \
  tests/integration/test_doctor.py \
  tests/performance/test_doctor_timing.py \
  tests/performance/test_import_timing.py
```

Expected outcome:

- zero network attempts during package import and `doctor`;
- no hostname, username, stable hardware identifier, raw environment, TOML content, or user-file
  content in output;
- CPU-only `doctor` completes within 5 seconds on the reference system;
- import p95 remains at or below 200 ms on the reference SSD system.

## 9. Run All Quality Gates

```bash
uv run ruff format --check .
uv run ruff check .
uv run pydoclint src tests
uv run codespell .
uv run pytest
```

Expected outcome: every command succeeds and no public method, function, class, module, CLI
command, argument, option, or example lacks English documentation.

## 10. Build and Inspect Artifacts

```bash
rm -rf dist
uv build --no-sources
uv run twine check dist/*
uv run check-wheel-contents dist/*.whl
```

Expected outcome:

- one source distribution and one wheel are built;
- metadata is valid;
- artifacts contain package code and required metadata only;
- artifacts do not contain tests, models, caches, or development-only files;
- the base artifact remains within the specified 5 MiB budget beyond declared dependencies.

Smoke-test the wheel outside the project environment:

```bash
WHEEL="$(ls dist/*.whl)"
uv run --isolated --no-project --with "$WHEEL" \
  python -c "import ceia_aisdk; print(ceia_aisdk.__version__)"
uv run --isolated --no-project --with "$WHEEL" ceia-aisdk --help
uv run --isolated --no-project --with "$WHEEL" ceia-aisdk doctor
```

Repeat with the source distribution:

```bash
SDIST="$(ls dist/*.tar.gz)"
uv run --isolated --no-project --with "$SDIST" \
  python -c "import ceia_aisdk; print(ceia_aisdk.__version__)"
```

Do not run `uv publish`; public PyPI publication is explicitly outside PRD-00.

## 11. Validate the Full Python Matrix

```bash
for version in 3.11 3.12 3.13; do
  uv python install "$version"
  uv run --python "$version" pytest
done
```

Expected outcome: all contract and behavior tests pass on every supported Python version.
