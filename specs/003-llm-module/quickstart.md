# Quickstart Validation: Local LLM Module and First Public Release

**Feature**: `003-llm-module`

This guide validates the completed PRD-02 implementation. It is not an implementation guide and
does not replace the automated test suite. Foundation and registry checks in
[001-sdk-foundations/quickstart.md](../../001-sdk-foundations/quickstart.md) and
[002-model-registry/quickstart.md](../../002-model-registry/quickstart.md) remain applicable.

## Prerequisites

- Linux x86_64
- `uv`
- Completed `001-sdk-foundations` and `002-model-registry`
- Tiny GGUF fixture for automated backend tests (`scripts/fetch-llm-test-fixture.sh`)
- Production `llm/small` pull and NVIDIA CUDA checks are manual on the reference machine

The examples use Python 3.13.

## 1. Synchronize Dependencies

```bash
uv python install 3.13
uv sync --python 3.13 --locked --all-groups --all-extras
uv lock --check
```

Expected outcome:

- `llama-cpp-python` is a runtime dependency;
- lockfile is unchanged after `--check`;
- no production weights are downloaded during sync.

## 2. Import Budget Still Holds

```bash
uv run python -c "import ceia_aisdk, sys; assert 'llama_cpp' not in sys.modules; print(ceia_aisdk.__version__)"
uv run python -c "from ceia_aisdk.llm import LLM; import sys; assert 'llama_cpp' not in sys.modules; print(LLM)"
```

Expected outcome:

- both commands print without loading `llama_cpp`;
- `GenerationError` and `CapabilityError` are importable from `ceia_aisdk`.

```bash
uv run pytest tests/contract/test_package_api.py tests/contract/test_llm_import_budget.py tests/performance/test_import_timing.py
```

## 3. Settings, Doctor Binding, and Help

```bash
uv run ceia-aisdk doctor --help
uv run ceia-aisdk doctor
```

Expected outcome:

- help mentions CUDA binding versus GPU visibility;
- copyable block contains `cuda_binding=yes` or `cuda_binding=no`;
- `optional_groups` no longer prints `cuda:reserved`;
- no new mandatory inference subcommand appears in root help.

```bash
uv run pytest tests/contract/test_cli_help.py tests/integration/test_doctor.py tests/unit/test_llm_settings.py
```

## 4. Fake-Backend Unit Matrix

```bash
uv run pytest tests/unit/test_llm_settings.py tests/unit/test_llm_devices.py tests/unit/test_llm_session.py tests/unit/test_llm_capabilities.py
```

Expected outcome:

- default alias is `llm/small@latest`;
- `device="cpu"` wins over a visible GPU;
- `device="auto"` plus oversized `size_gb` selects CPU and a WARNING (VRAM fallback);
- explicit CUDA oversized alias raises `DeviceError`;
- tools on an alias without `tool_use` raise `CapabilityError`;
- session retains two turns in memory without `llama_cpp`.

## 5. Real-Backend Smoke (Tiny GGUF)

```bash
./scripts/fetch-llm-test-fixture.sh
uv run pytest tests/integration/test_llm_chat.py tests/integration/test_llm_stream_session.py tests/integration/test_llm_device_cpu.py tests/integration/test_llm_offline.py tests/integration/test_async_llm.py
```

Expected outcome:

- `LLM().chat` against the fixture catalog returns a nonempty string;
- `.stream` yields at least one chunk;
- forced `device="cpu"` runs;
- `CEIA_AISDK_OFFLINE=1` on a cache miss fails within 1 s with `DownloadError` and does not
  import `llama_cpp`;
- at least one `AsyncLLM` smoke test completes under an asyncio timeout.

Session coreference on the tiny model may be weak; use the unit session test plus the manual
checklist below for production quality.

## 6. Packaging Without Weights

```bash
uv build --no-sources
uv run pytest tests/contract/test_llm_packaging.py tests/integration/test_installed_artifacts.py
```

Expected outcome:

- wheel and sdist contain `ceia_aisdk.llm` and the catalog YAML;
- artifacts contain no `.gguf` weight files;
- isolated install still forbids `llama_cpp` on `import ceia_aisdk`.

## 7. Quality Gates

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pydoclint src
uv run pytest
uv build --no-sources
```

All contributor commands use `uv`.

## 8. Manual Reference Checklist (not CI)

On a clean Linux x86_64 CPU machine with network:

1. Install from the public index (or a locally built wheel standing in for it before publish):
   `pip install ceia-aisdk`.
2. Time `LLM().chat("Say only: ok")` including the `llm/small` pull. Target ≤ 15 minutes.
   CUDA compilation is not in this clock.
3. Confirm a TTY progress indication on first obtain.
4. Warm first token of `.chat` / `.stream` ≤ 10 s.
5. Two-turn session on real `llm/small` shows awareness of the first turn.
6. On the reference NVIDIA machine with the documented `[cuda]` extra: `doctor` shows
   `cuda_binding=yes`; `device="auto"` chat logs `cuda`; forced `cpu` still works.

## 9. Publish `0.1.0`

After gates and the CPU manual checklist:

```bash
# version in pyproject.toml is 0.1.0
uv build --no-sources
uv publish
```

Expected outcome: `ceia-aisdk==0.1.0` on the public index, README quickstart visible, Linux
classifiers only, `[cuda]` extra documented, no weights in the files.
