# Implementation Plan: Model Registry and Cache

**Branch**: `002-model-registry` (feature identifier; Git worktree is currently on `main`) |
**Date**: 2026-09-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-model-registry/spec.md`

## Summary

Add an opaque, versioned model registry to `ceia-aisdk` so developers can resolve `llm/small@N`,
download a single integrity-checked artifact, and reuse a deterministic cache under
`AISDKConfig.cache_dir`. The increment ships a bundled YAML catalog (no signatures, no mirrors),
an `httpx` downloader with resume and mandatory SHA-256, `fcntl` locks, the
`ceia-aisdk model` command group, and the `resolve` / `ensure_local` / `get_public_metadata`
contract for later inference modules. Weights stay out of the wheel. The package is not
published to PyPI.

## Technical Context

**Language/Version**: Python 3.11, 3.12, and 3.13

**Primary Dependencies**: Existing Typer and Rich at the CLI boundary; `httpx` for resumable
HTTP downloads (lazy-imported); PyYAML `SafeLoader` for the catalog; Python standard library for
paths, SHA-256, `fcntl` locks, `os.replace`, logging, and the test fixture HTTP server

**Storage**: Runtime model cache at `<cache_dir>/models/` with opaque `.bin` files, JSON
sidecars, lock files, and `.tmp` partials; bundled package-data catalog YAML; optional catalog
override via `CEIA_AISDK_CATALOG`; no database

**Testing**: pytest unit, contract, integration, opacity, performance, and packaging tests;
pytest-socket remains default-off except loopback download tests marked `enable_socket`; a
generated ≥ 16 MiB fixture served locally with `Range` support; Ruff, pydoclint, codespell,
check-wheel-contents, and Twine checks unchanged in role

**Target Platform**: Linux x86_64, Ubuntu 22.04+ reference, GitHub Actions Ubuntu x86_64 for
Python 3.11-3.13

**Project Type**: Single Python library with a console-script CLI

**Performance Goals**: Warm-cache `pull` / `ensure_local` at or below 2 seconds with zero HTTP
GET; offline cache-miss failure at or below 100 ms with zero sockets; foundation p95 import at
or below 200 ms without loading `httpx` or PyYAML

**Constraints**: Exactly one URL per artifact; SHA-256 required; no host failover; no catalog
signature; no `LicenseError`; public cataloged output never reveals origin URL or upstream
names; downloader cannot write outside `cache_dir/models` and `.tmp`; weights never enter wheel
or sdist; no public PyPI upload; `offline` now blocks downloads

**Scale/Scope**: One catalog schema, one bundled document pinning published `llm/small@1`,
`llm/medium@1`, and `llm/large@1` artifacts, CLI group of six commands plus `--essentials`
(`llm/small` required), three public registry functions, two new error types, documented
`hf://` and path bypasses. CI uses local fixtures, not production weights.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

### Pre-Research Gate

- **I. PyPI-Ready Library — PASS**: The registry is part of the installable package. The catalog
  YAML is metadata package data. Model weights and caches are runtime-only and are excluded from
  artifacts. Publication remains prohibited in this increment.
- **II. SpecKit-First Development — PASS**: `spec.md` exists, has no unresolved clarification
  markers, and this plan precedes tasks and implementation.
- **III. Test-First Development — PASS**: Research and contracts define failing tests for
  resolve, resume, tamper, opacity, offline, concurrency, essentials, override, and packaging
  before production code. Tasks must preserve red-green-refactor ordering.
- **IV. English-Only Repository — PASS**: Specification, plan, research, data model, contracts,
  quickstart, source, docstrings, CLI help, errors, and tests are required to be in English.
- **V. Complete Public Interface Documentation — PASS**: `resolve`, `ensure_local`,
  `get_public_metadata`, new errors, and every `model` command require English docstrings or
  help with parameters, returns/exits, exceptions, side effects, and executable examples. Root
  help must list `model`.
- **Packaging and Tooling — PASS**: `httpx` and `pyyaml` are added with `uv`; `uv.lock` is
  committed; builds remain `uv build`.
- **Quality Gates — PASS**: Existing CI gates remain; download tests opt into loopback sockets
  without weakening default socket blocking.

No constitutional violation requires an exception.

### Post-Design Gate

- Phase 1 contracts stay inside the specification: one URL, SHA-256, no signatures, no mirrors,
  no license blocking, no PyPI upload.
- Public `ResolvedAlias` and `PublicModelMetadata` omit origin fields, preserving opacity at the
  type boundary.
- `httpx` and PyYAML are isolated from `import ceia_aisdk`, preserving the foundation import
  contract.
- Cache writes are confined to `models/` and `models/.tmp` under `cache_dir`.
- All contributor commands in the quickstart use `uv`.
- TDD evidence remains an implementation gate to be encoded by `/speckit-tasks`.

**Result**: PASS. The design is ready for task generation.

## Project Structure

### Documentation (this feature)

```text
specs/002-model-registry/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/
│   └── requirements.md
├── contracts/
│   ├── catalog.md
│   ├── cli.md
│   └── python-api.md
└── tasks.md                 # Created by /speckit-tasks, not by this command
```

### Source Code (repository root)

```text
.
├── pyproject.toml           # add httpx, pyyaml
├── uv.lock
├── README.md                # registry increment
├── src/ceia_aisdk/
│   ├── __init__.py          # export ModelNotFoundError, DownloadError only
│   ├── errors.py            # add ModelNotFoundError, DownloadError
│   ├── cli.py               # mount model subapp
│   ├── _model_cli.py        # Typer commands for model *
│   └── registry/
│       ├── __init__.py      # resolve, ensure_local, get_public_metadata
│       ├── _internal_catalog.yaml
│       ├── catalog.py
│       ├── downloader.py    # lazy httpx
│       └── cache.py
└── tests/
    ├── contract/
    │   ├── test_model_cli_help.py
    │   ├── test_registry_api.py
    │   └── test_registry_opacity.py
    ├── integration/
    │   ├── test_model_download.py
    │   ├── test_model_cli.py
    │   ├── test_model_resume.py
    │   ├── test_model_offline.py
    │   ├── test_model_concurrency.py
    │   ├── test_model_essentials.py
    │   ├── test_catalog_override.py
    │   └── test_model_bypass.py
    ├── performance/
    │   ├── test_warm_cache.py
    │   └── test_offline_miss.py
    └── unit/
        ├── test_registry_resolve.py
        ├── test_registry_catalog.py
        ├── test_registry_cache.py
        └── test_registry_sanitize.py
```

**Structure Decision**: Keep the single `src`-layout package. Registry internals follow the
PRD module split (`catalog`, `downloader`, `cache`) with no `signing.py`. CLI rendering stays
out of `import ceia_aisdk`. Tests stay separated by purpose so resolve/schema units stay
socket-free while resume and concurrency tests opt into loopback HTTP.

## Complexity Tracking

No constitutional violations or additional architectural layers require justification.
