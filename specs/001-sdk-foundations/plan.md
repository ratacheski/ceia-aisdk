# Implementation Plan: CEIA AI SDK Operational Foundations

**Branch**: `001-sdk-foundations` (feature identifier; Git worktree is currently on `main`) |
**Date**: 2026-09-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-sdk-foundations/spec.md`

## Summary

Build the locally installable foundation of `ceia-aisdk` as a Python library and CLI for Linux
x86_64. The increment provides layered immutable configuration, namespaced logging, actionable
public errors, deterministic CPU/NVIDIA device selection, lightweight package imports, and a
privacy-preserving `ceia-aisdk doctor` command. The project uses a `src` layout, `uv_build`, Typer
and Rich at the CLI boundary, standard-library configuration and hardware probing, and a
test-first workflow executed entirely through `uv`. This feature produces local wheel and source
artifacts but does not publish them to PyPI.

## Technical Context

**Language/Version**: Python 3.11, 3.12, and 3.13

**Primary Dependencies**: Typer and Rich at the CLI boundary; Python standard library for
configuration, TOML parsing, logging, metadata, subprocess execution, paths, and platform
inspection; `uv_build` as the build backend

**Storage**: Optional read-only user configuration at `~/.ceia-aisdk/config.toml`; no database,
model cache, or SDK-managed persistent state in this feature

**Testing**: pytest for unit, contract, integration, packaging, privacy, and performance tests;
pytest-socket for in-process network blocking; Ruff, pydoclint, codespell,
check-wheel-contents, and Twine checks as development-only quality tools

**Target Platform**: Linux x86_64, with Ubuntu 22.04 or later as the supported reference and
GitHub Actions on Ubuntu x86_64 for Python 3.11-3.13

**Project Type**: Single Python library with a console-script CLI

**Performance Goals**: p95 package import at or below 200 ms on reference SSD storage;
`doctor` completion at or below 5 seconds; local installation at or below 60 seconds in at least
95% of clean reference runs; GPU memory reporting within 256 MiB of a near-simultaneous reference
reading

**Constraints**: Base distribution adds no more than 5 MiB beyond declared dependencies; import
must not load inference backends; import and `doctor` make zero network attempts; NVIDIA probing
times out after 2 seconds; automatic GPU probe failure falls back quietly to CPU; public failures
always contain remediation; no user-file contents, host identity, or telemetry may be emitted;
no public PyPI upload occurs in this feature

**Scale/Scope**: One package, one root CLI, one `doctor` subcommand, four configuration fields,
CPU plus local NVIDIA discovery, three public error classes at most, and a Python 3.11-3.13 CI
matrix; no inference, registry, server, application launcher, or desktop packaging

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

### Pre-Research Gate

- **I. PyPI-Ready Library — PASS**: The design keeps valid wheel and source builds at every
  increment, excludes runtime assets, and explicitly prohibits publication during PRD-00.
- **II. SpecKit-First Development — PASS**: `spec.md` exists, has no unresolved clarification
  markers, and this plan precedes tasks and implementation.
- **III. Test-First Development — PASS**: The design defines unit, contract, integration,
  performance, privacy, and package tests. Tasks must preserve red-green-refactor ordering.
- **IV. English-Only Repository — PASS**: The specification, plan, research, contracts, data
  model, quickstart, source, docstrings, CLI text, and tests are required to be in English.
- **V. Complete Public Interface Documentation — PASS**: Public contracts require docstrings for
  modules, classes, functions, and all methods, plus complete root and subcommand help with
  executable examples.
- **Packaging and Tooling — PASS**: Dependency changes, locking, command execution, builds, and
  validation use `uv`; the project uses `uv_build`, `pyproject.toml`, and a committed `uv.lock`.
- **Quality Gates — PASS**: CI will enforce lock consistency, linting, docstring checks, tests,
  help/example contracts, package builds, artifact inspection, and installed-package smoke tests.

No constitutional violation requires an exception.

### Post-Design Gate

- All Phase 1 contracts remain within the approved specification and contain no inference,
  registry, publication, telemetry, or unsupported-platform behavior.
- The data model is dependency-light and immutable at public boundaries.
- CLI rendering is isolated from diagnostic semantics, preserving import performance and
  deterministic contract tests.
- All contributor commands in the quickstart use `uv`.
- TDD evidence remains an implementation gate to be encoded by `/speckit-tasks`.

**Result**: PASS. The design is ready for task generation.

## Project Structure

### Documentation (this feature)

```text
specs/001-sdk-foundations/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/
│   └── requirements.md
├── contracts/
│   ├── cli.md
│   ├── configuration.md
│   └── python-api.md
└── tasks.md                 # Created by /speckit-tasks, not by this command
```

### Source Code (repository root)

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml
├── pyproject.toml
├── uv.lock
├── README.md
├── src/
│   └── ceia_aisdk/
│       ├── __init__.py
│       ├── _diagnostics.py
│       ├── _logging.py
│       ├── cli.py
│       ├── config.py
│       ├── errors.py
│       └── hardware.py
└── tests/
    ├── contract/
    │   ├── test_cli_help.py
    │   ├── test_package_api.py
    │   └── test_public_errors.py
    ├── integration/
    │   ├── test_cli_entrypoint.py
    │   ├── test_doctor.py
    │   └── test_installed_artifacts.py
    ├── performance/
    │   ├── test_doctor_timing.py
    │   └── test_import_timing.py
    └── unit/
        ├── test_config.py
        ├── test_diagnostics.py
        ├── test_hardware.py
        └── test_logging.py
```

**Structure Decision**: Use a single `src`-layout Python project. Public modules contain the
configuration, hardware, error, and CLI contracts. Private modules separate diagnostic data
collection and library-safe logging from Rich rendering. Tests are separated by purpose so that
fast unit and contract suites can drive TDD while installed-artifact and performance checks retain
their distinct environment requirements.

## Complexity Tracking

No constitutional violations or additional architectural layers require justification.
