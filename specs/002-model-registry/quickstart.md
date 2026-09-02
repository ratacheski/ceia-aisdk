# Quickstart Validation: Model Registry and Cache

**Feature**: `002-model-registry`

This guide validates the completed PRD-01 implementation. It is not an implementation guide and
does not replace the automated test suite. Foundation checks in
[001-sdk-foundations/quickstart.md](../../001-sdk-foundations/quickstart.md) remain applicable.

## Prerequisites

- Linux x86_64
- `uv`
- Completed `001-sdk-foundations` install (`uv sync --locked`)
- Loopback network only for automated download scenarios (tests start a local fixture server).
  Production aliases live on the `ceia-aisdk` Hugging Face organization; this guide does not
  require pulling those multi-gigabyte files.

The examples use Python 3.13.

## 1. Synchronize Dependencies

```bash
uv python install 3.13
uv sync --python 3.13 --locked --all-groups --all-extras
uv lock --check
```

Expected outcome:

- `httpx` and `pyyaml` are runtime dependencies;
- lockfile is unchanged after `--check`;
- no model weights are downloaded during sync.

## 2. Import Budget Still Holds

```bash
uv run python -c "import ceia_aisdk, sys; assert 'httpx' not in sys.modules; assert 'yaml' not in sys.modules; print(ceia_aisdk.__version__)"
```

Expected outcome:

- version prints;
- `httpx` and `yaml` are not loaded by `import ceia_aisdk`;
- `ModelNotFoundError` and `DownloadError` are importable from `ceia_aisdk`.

```bash
uv run pytest tests/contract/test_package_api.py tests/performance/test_import_timing.py
```

## 3. Discover the Model Command

```bash
uv run ceia-aisdk --help
uv run ceia-aisdk model --help
uv run ceia-aisdk model pull --help
uv run ceia-aisdk model info --help
```

Expected outcome:

- root help lists `doctor` and `model`;
- every `model` subcommand help includes English examples;
- `model info --help` states that catalog authenticity is not verified and integrity is the
  artifact checksum.

```bash
uv run pytest tests/contract/test_cli_help.py tests/contract/test_model_cli_help.py
```

## 4. Resolve Without Downloading

Point tests at a local catalog fixture (the automated suite does this). Manual equivalent:

```bash
uv run python -c "from ceia_aisdk.registry import resolve; print(resolve('llm/small'))"
```

Expected outcome:

- canonical `llm/small@N` prints with public metadata;
- no cache file is created;
- `repr` contains no download URL.

```bash
uv run pytest tests/unit/test_registry_resolve.py tests/contract/test_registry_api.py
```

## 5. Pull, Inspect, and Locate

The integration suite starts a loopback server and a ≥ 16 MiB fixture:

```bash
uv run pytest tests/integration/test_model_download.py tests/integration/test_model_cli.py
```

Expected outcome:

- `model pull llm/small` stores an opaque path under `$CEIA_AISDK_CACHE_DIR/models/llm/`;
- `model info llm/small` shows only the public block;
- `model where llm/small` prints an absolute path;
- `model list` shows the alias and size;
- `model verify` exits `0`;
- a second pull completes in ≤ 2 s with zero HTTP GET requests.

## 6. Resume, Tamper, Offline, and Concurrency

```bash
uv run pytest tests/integration/test_model_resume.py tests/integration/test_model_offline.py tests/integration/test_model_concurrency.py
```

Expected outcome:

- interruption after ≥ 8 MiB resumes with `Range` and matches SHA-256;
- a one-byte tamper fails `verify` and is not promoted;
- `CEIA_AISDK_OFFLINE=1` on a cache miss fails within 100 ms with `DownloadError` and no socket;
- two concurrent pulls leave one valid file.

## 7. Essentials, Override, and Bypass

```bash
uv run pytest tests/integration/test_model_essentials.py tests/integration/test_catalog_override.py tests/integration/test_model_bypass.py
```

Expected outcome:

- `--essentials` pulls `llm/small` when present and warns instead of crashing when an essential
  name is absent;
- `CEIA_AISDK_CATALOG` pointing at a valid local YAML uses only that catalog;
- invalid schema raises `DownloadError` whose remediation names the schema;
- local-path and `hf://` bypasses store `source=bypass` custom entries without rewriting catalog
  opaque names.

## 8. Opacity and Package Contents

```bash
uv run pytest tests/contract/test_registry_opacity.py tests/integration/test_installed_artifacts.py
```

Expected outcome:

- `model info` output and `str(DownloadError)` for cataloged aliases contain no
  `huggingface.co`, production repository, or upstream filename;
- the wheel contains `_internal_catalog.yaml` and no weight payloads;
- isolated wheel install still exposes `ceia-aisdk model --help`.

## 9. Quality Gates

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pydoclint src
uv run pytest
uv build --no-sources
```

All contributor commands use `uv`. This feature does not upload to PyPI.
