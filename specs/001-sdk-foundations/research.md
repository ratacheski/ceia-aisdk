# Research: CEIA AI SDK Operational Foundations

**Feature**: `001-sdk-foundations`
**Date**: 2026-09-01

## 1. Package Layout and Build Backend

**Decision**: Use a single Python project with a `src/ceia_aisdk/` package, `uv_build` as the
build backend, static version `0.1.0.dev0`, and `pyproject.toml` as the package metadata source.
Expose `ceia_aisdk.__version__` through `importlib.metadata.version("ceia-aisdk")`. Build both a
wheel and source distribution with `uv build --no-sources`. Reserve `cuda = []` as an empty
optional dependency group in PRD-00.

**Rationale**: The `src` layout ensures tests exercise the installed package rather than importing
files accidentally from the checkout. `uv_build` is designed for pure-Python packages and
provides strict, low-configuration defaults. A static version avoids VCS-version plugins and
keeps package metadata and the runtime version in one source. An empty CUDA extra accurately
reserves the public name without claiming to install a functional runtime.

**Alternatives considered**:

- Hatchling: useful for advanced hooks or VCS-derived versions, but unnecessary for this
  pure-Python foundation.
- Setuptools: mature and extensible, but adds configuration complexity not required by the
  current package.
- Flat package layout: rejected because imports can succeed from the checkout while built
  artifacts remain incomplete.
- Duplicating the version in `__init__.py`: rejected because the two values can diverge.
- Adding a placeholder CUDA package: rejected because it would produce misleading metadata.

**Risks and validation**:

- A pure-Python wheel is technically portable even though the supported product target is Linux
  x86_64. Metadata, documentation, `doctor`, and CI must state and enforce the supported scope.
- The empty CUDA extra must be described as reserved, not functional.
- CI must inspect the wheel and sdist, install each in isolation, and compare
  `ceia_aisdk.__version__` with distribution metadata.

**References**:

- [uv build backend](https://docs.astral.sh/uv/concepts/build-backend/)
- [uv project builds](https://docs.astral.sh/uv/concepts/projects/build/)
- [PyPA src layout guidance](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [PyPA single-source version guidance](https://packaging.python.org/en/latest/discussions/single-source-version/)

## 2. Dependency and Tool Management

**Decision**: Use `uv` for all project dependency changes, locking, synchronization, command
execution, builds, isolated artifact tests, and future publication. Put Typer and Rich in runtime
dependencies. Put pytest, pytest-socket, Ruff, pydoclint, codespell, check-wheel-contents, and
Twine in the development dependency group. Commit `uv.lock` and require
`uv lock --check` plus `uv sync --locked` in CI.

**Rationale**: This directly implements the constitution and keeps the runtime boundary small.
Typer and Rich are required by PRD-00 but remain isolated from package import paths. Development
quality tools do not enter distribution metadata as runtime requirements.

**Alternatives considered**:

- Mixing `pip`, virtualenv, and `uv`: rejected because it creates multiple environment and lock
  semantics.
- Legacy `tool.uv.dev-dependencies`: rejected in favor of standardized dependency groups.
- tox or tox-uv: deferred because the GitHub Actions Python matrix and direct `uv` commands are
  sufficient for this small project.

**Risks and validation**:

- A synchronized lockfile does not prove dependency freshness; upgrades must be deliberate.
- Every contributor and CI command documented by the project must execute through `uv`.
- Artifact validation must run outside the source checkout to detect undeclared files.

## 3. Layered Configuration

**Decision**: Represent effective configuration as a frozen, slotted `AISDKConfig` dataclass with
`device: str`, `cache_dir: Path`, `log_level: str`, and `offline: bool`. Construct snapshots
through `AISDKConfig.load(...)`, resolving each field independently in this order: explicit
argument, matching environment variable, `[core]` TOML value, default. A `None` argument means
that the explicit layer did not provide the field.

Use only the Python standard library: `tomllib`, `dataclasses`, `pathlib`, and `os`.

Validation rules:

- `device`: exactly `auto`, `cpu`, `cuda`, or `cuda:N`, where `N` is a canonical nonnegative
  decimal integer.
- `cache_dir`: a nonempty string or path-like value without NUL; apply `expanduser()` without
  creating or resolving the path.
- `log_level`: exactly `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`.
- `offline`: explicit and TOML values must be booleans; environment values must be `0` or `1`.
- Defaults: `auto`, expanded `~/.ceia-aisdk`, `WARNING`, and `False`.

A missing or empty TOML file is valid. Malformed TOML, unreadable files, and invalid winning
values raise `ConfigError` with source and remediation but without echoing file contents or raw
secrets. Unknown sections and keys are ignored in PRD-00 so later features can extend the file
without breaking older foundation code.

**Rationale**: An immutable snapshot cannot drift after validation. Field-by-field resolution
supports mixed sources correctly. Standard-library parsing keeps import time and package size
small. Validating only the winning value honors precedence: an invalid lower-priority value must
not defeat a valid explicit override.

**Alternatives considered**:

- Mutable configuration: rejected because it allows invalid state after construction.
- Pydantic, Dynaconf, or another configuration package: rejected because four fields do not
  justify the dependency and import cost.
- Environment-variable expansion or `Path.resolve()`: rejected because they add surprising
  filesystem-dependent behavior.
- Permissive booleans and case normalization: rejected because deployment mistakes become
  ambiguous.

**Risks and validation**:

- Strict case and boolean parsing require error messages that list accepted values.
- `expanduser()` failure must become a privacy-safe `ConfigError`.
- Tests must cover every source, mixed-source resolution, invalid shadowed values, empty
  environment variables, malformed files, and a temporary home directory.

## 4. Logging and Public Errors

**Decision**: Every module uses `logging.getLogger(__name__)`. The package installs only a
`NullHandler` and never calls `basicConfig`, changes the root logger, or installs a console
handler during import. A private helper may set the `ceia_aisdk` namespace level when invoked by
the CLI.

Define `AISDKError` as the root public exception. Its constructor requires nonempty `message` and
`remediation` text, and `.remediation` remains publicly accessible. `ConfigError` and
`DeviceError` derive directly from it.

**Rationale**: Library consumers retain control over handlers and formatting. A single error
contract gives the CLI and future modules a stable way to display next actions.

**Alternatives considered**:

- Configuring the root logger: rejected because a library must not alter its host application's
  logging policy.
- Warning on automatic CPU fallback: rejected because CPU is a supported state.
- Native exceptions at public boundaries: rejected because they lack stable remediation.

**Risks and validation**:

- Namespace-level logging is process-global, so configuration must be explicit and idempotent.
- Tests must prove root logger state is unchanged and every public exception has nonempty
  remediation.

## 5. NVIDIA Detection and Device Selection

**Decision**: Probe NVIDIA hardware with one local process invocation per snapshot:

```text
nvidia-smi --query-gpu=index,uuid,name,memory.total,memory.free,compute_mode,mig.mode.current \
  --format=csv,noheader,nounits
```

Execute a fixed argument vector with `shell=False`, captured output, English locale, no input,
and a 2-second timeout. Parse with the standard `csv` module. Require seven fields, unique
nonnegative indices, nonempty UUID and name, integer MiB values, and
`0 <= free_vram_mib <= total_vram_mib`. Sort by numeric index.

`device="cpu"` skips probing. `auto` chooses `cuda:N` for the lowest usable index and returns
`cpu` on any probe failure. `cuda` chooses the lowest usable index but raises `DeviceError` when
none exists. `cuda:N` requires that exact index. Compute-prohibited GPUs and enabled MIG mode are
reported but not selected in PRD-00.

**Rationale**: `nvidia-smi` provides name and total/free VRAM without importing or depending on
an inference framework. One snapshot prevents inconsistent selection and display. CSV parsing
handles quoted names safely, while the timeout isolates driver/tool failures.

**Alternatives considered**:

- `torch.cuda`, CuPy, or PyCUDA: rejected because they are heavyweight inference dependencies.
- Python NVML bindings: reliable but unnecessary as a base runtime dependency.
- Direct `ctypes` calls into NVML or CUDA: rejected because ABI faults and hangs are harder to
  isolate safely in process.
- `lspci`, sysfs, or `/proc`: insufficient for free VRAM and driver usability.

**Risks and validation**:

- The reported `nvidia-smi` index is an NVML index and may differ from a future framework ordinal
  under container remapping or `CUDA_VISIBLE_DEVICES`. PRD-00 documents that meaning; PRD-02 must
  map by UUID if backend ordinals differ.
- Free VRAM is instantaneous. Compare reference readings immediately around `doctor` and accept
  the specified 256 MiB tolerance.
- A successful management probe does not prove a future inference backend was compiled for CUDA.
- Tests must cover missing executables, timeouts, nonzero exits, malformed or oversized output,
  quoted CSV names, duplicate or unordered indices, prohibited compute, MIG, and nonexistent
  forced indices.

## 6. CLI and Diagnostic Report

**Decision**: Implement the console script with Typer and render interactive output with Rich.
Keep Typer and Rich imports out of `ceia_aisdk.__init__`. Build a semantic diagnostic report in a
private module and render it separately:

- interactive terminal: readable Rich sections;
- redirected or noninteractive output: deterministic plain text without ANSI;
- every mode: fixed-order ASCII “copy this” block.

The root command and `doctor` must each provide a purpose, short help, and an English Examples
epilog. Every argument or option must document purpose, required status, default, constraints,
and an example. PRD-00 adds no feature-specific `doctor` options.

The report excludes hostname, username, IP addresses, full environment variables, current
working directory, file contents, serial numbers, and telemetry identifiers. Home-directory
paths are normalized to `~`. It reports the reserved CUDA extra as reserved rather than
installed.

Exit codes:

- `0`: help or a usable foundation;
- `1`: diagnosis completed but the foundation is not usable;
- `2`: invalid CLI invocation, reserved by the CLI framework.

**Rationale**: Separating data from presentation makes privacy, exit codes, plain output, and
field order independently testable. CLI-only Rich imports preserve the package import budget.

**Alternatives considered**:

- Rich snapshots as the sole contract: rejected because terminal width and library versions make
  full ANSI snapshots brittle.
- A new `--plain` public option: rejected because automatic non-TTY behavior satisfies the
  specification without expanding the public interface.
- `rich-click`: rejected because Typer already integrates Rich.

**Risks and validation**:

- Terminal rendering must be tested at representative widths, with `TERM=dumb`, `NO_COLOR`, a
  redirected stream, and a pseudo-terminal.
- An empty optional extra cannot prove installation. The diagnostic must use the specification's
  “available/reserved” terminology.
- Help contracts and examples require recursive tests over the complete command tree.

## 7. TDD, Quality Gates, and Continuous Integration

**Decision**: Use pytest as the test runner and preserve red-green-refactor ordering in feature
tasks. Separate unit, public-contract, installed-entry-point, package-artifact, privacy,
performance, and optional reference-GPU validations. Use a GitHub Actions matrix on Linux x86_64
for Python 3.11, 3.12, and 3.13 with `fail-fast: false`; run lint, documentation, build, and
artifact inspection once on Python 3.13, and package smoke tests across all supported versions.

Required automated gates:

- `uv lock --check` and `uv sync --locked`;
- Ruff format, lint, and docstring rules;
- pydoclint for docstring signature consistency;
- codespell plus human English-language review;
- complete pytest suite with sockets disabled unless a test opts in;
- recursive CLI help and executable-example contracts;
- fresh-process import isolation and timing;
- external timeout around `doctor`;
- `uv build --no-sources`, Twine metadata checks, artifact-content checks, size checks, and
  isolated wheel/sdist installation.

**Rationale**: The test layers separate fast feedback from environment-sensitive acceptance.
Fresh processes are required for meaningful import and module-loading checks. Installed-artifact
tests catch packaging failures that source-tree tests cannot.

**Alternatives considered**:

- Testing only through Typer's in-process runner: rejected because it cannot validate the
  installed entry point, process environment, import isolation, or terminal behavior.
- pytest-benchmark for imports: rejected because reused interpreters distort import measurements.
- A GPU-required hosted CI gate: rejected because standard hosted runners have no NVIDIA device.

**Risks and validation**:

- Shared CI timing is noisy. Reference-machine thresholds remain normative; CI records timing and
  detects major regressions without treating small host variance as a product failure.
- In-process socket blocking does not automatically cover child processes. Installed-command
  tests must inject a child-process socket blocker or use Linux syscall observation.
- CI cannot prove that a developer observed the red state. Review must require explicit TDD
  evidence in the change history or task record.
- Real-GPU validation remains optional in PRD-00 and must be recorded as a reference-machine
  result when no suitable runner exists.
