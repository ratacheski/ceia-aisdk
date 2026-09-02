# Feature Specification: CEIA AI SDK Operational Foundations

**Feature Branch**: `main` (no branch was created; there is no `before_specify` hook)

**Created**: 2026-09-01

**Status**: Draft

**Input**: PRD-00 (`docs/prd/00-foundations.md`) and decisions ratified in the PRD program on 2026-09-01

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install and Recognize the SDK Locally (Priority: P1)

As a developer who has cloned the repository, I want to install the SDK in my local environment and recognize its public identifiers so that I can start developing without depending on a publication to the public index.

**Why this priority**: All other capabilities depend on a locally installable and importable package with a recognizable command-line interface.

**Independent Test**: On a compatible Linux x86_64 machine, install the project from the repository, import `ceia_aisdk`, check its version, and run `ceia-aisdk --help`; this demonstrates the product's minimum contract without depending on the other stories.

**Acceptance Scenarios**:

1. **Given** a Linux x86_64 machine with a supported Python version and a clone of the repository, **When** the developer installs the project in editable mode, **Then** the `ceia_aisdk` package is importable and the `ceia-aisdk` command is available.
2. **Given** the package installed locally, **When** the developer checks the command help, **Then** the help displays at least the `doctor` subcommand.
3. **Given** the package installed locally, **When** the developer checks the version through the package or the diagnostic, **Then** both surfaces display the same version.
4. **Given** an attempt to locate a public version resulting from this feature, **When** the developer checks the public index, **Then** this feature neither requires nor announces a publication; the first public release remains reserved for PRD-02.

---

### User Story 2 - Diagnose Machine Readiness (Priority: P1)

As a developer or maintainer, I want to run a single, copyable diagnostic to determine whether the foundation is usable and attach reproducible information to an issue.

**Why this priority**: The diagnostic reduces triage time and establishes a common way to verify the environment, configuration, and hardware before any inference module.

**Independent Test**: Run `ceia-aisdk doctor` on a CPU-only Linux x86_64 machine and verify its content, duration, lack of network access, and exit code.

**Acceptance Scenarios**:

1. **Given** a compatible installation on a machine without an available NVIDIA GPU, **When** the developer runs `ceia-aisdk doctor`, **Then** the diagnostic completes successfully, selects CPU, and displays all required information within 5 seconds.
2. **Given** a detectable NVIDIA GPU, **When** the developer runs the diagnostic, **Then** each GPU is displayed with its index, name, total memory, and free memory, together with the selected device.
3. **Given** a configuration that forces CUDA without a usable GPU, **When** the developer runs the diagnostic, **Then** the command exits with a nonzero code and explains how to use CPU or fix the CUDA environment.
4. **Given** any diagnostic run, **When** the output is produced, **Then** there is a clearly delimited block that can be copied into an issue without containing personal file contents.

---

### User Story 3 - Configure the SDK Predictably (Priority: P1)

As a developer, I want to define the device, cache directory, log level, and offline mode in layers so that I can reuse the same code on a workstation and in continuous integration.

**Why this priority**: Stable precedence prevents environment-dependent behavior and will serve as the configuration contract for subsequent modules.

**Independent Test**: Provide conflicting values in explicit arguments, environment variables, the local file, and defaults, separately verifying the winning source for each option.

**Acceptance Scenarios**:

1. **Given** different values for the same option in all four layers, **When** the configuration is loaded, **Then** the following order prevails: explicit arguments, environment variables, local file, and defaults.
2. **Given** that the local configuration file does not exist, **When** the configuration is loaded, **Then** the SDK operates normally with environment variables and defaults.
3. **Given** that no layer defines values, **When** the configuration is loaded, **Then** the cache points to `~/.ceia-aisdk` with the path expanded, the device is `auto`, offline mode is disabled, and the process starts logging at `WARNING`.
4. **Given** `CEIA_AISDK_OFFLINE=1`, **When** the configuration is loaded, **Then** the `offline` option is enabled without adding download behavior or network blocking for future modules in this feature.

---

### User Story 4 - Select CPU or CUDA Safely (Priority: P2)

As a developer, I want the SDK to detect available hardware and select a valid device so that I do not have to configure the GPU manually.

**Why this priority**: Automatic selection improves the initial experience, but the foundation remains usable with CPU only.

**Independent Test**: Simulate environments with no GPU, one GPU, multiple GPUs, and unavailable forced CUDA, verifying the returned device and metadata.

**Acceptance Scenarios**:

1. **Given** that no usable NVIDIA GPU is detected and the device is set to `auto`, **When** the device is resolved, **Then** the result is `cpu` with no exception and no log at `WARNING` level or higher.
2. **Given** one or more usable NVIDIA GPUs and the device set to `auto`, **When** the device is resolved, **Then** a GPU is selected deterministically and the result identifies CUDA and its index.
3. **Given** explicitly configured `device="cuda"` or `device="cuda:N"` and the target is unavailable, **When** the device is resolved, **Then** a `DeviceError` occurs with nonempty remediation.
4. **Given** a detected GPU, **When** its information is queried, **Then** its index, name, total memory, and free memory are made available without loading an inference backend.

---

### User Story 5 - Receive Actionable Failures (Priority: P2)

As a developer, I want public failures to indicate the next action needed to resolve the problem without first relying on a stack trace from an internal library.

**Why this priority**: Actionable errors reduce support needs and form a reusable contract for subsequent modules.

**Independent Test**: Trigger an invalid device selection and verify its public type, message, and remediation without running the complete diagnostic.

**Acceptance Scenarios**:

1. **Given** a public device-selection failure, **When** it is caught, **Then** it belongs to the `AISDKError` hierarchy and exposes `.remediation` as nonempty text.
2. **Given** an invalid configuration input, **When** the SDK rejects it, **Then** the developer receives an actionable explanation without exposure of personal file contents.
3. **Given** a machine without a GPU and automatic selection, **When** the SDK selects CPU, **Then** no public failure is raised because the absence of a GPU is a supported state.

### Edge Cases

- The `~/.ceia-aisdk/config.toml` file is missing, empty, unreadable, or contains an invalid value.
- An environment variable is set to an empty string or contains a value outside the accepted domain.
- The home directory uses a nonstandard path, and `~/.ceia-aisdk` must be expanded correctly.
- The local GPU detection tool is missing, times out, or returns partial output.
- There are multiple GPUs, a disabled GPU, or a nonexistent `cuda:N` index.
- GPU memory changes between two readings; the diagnostic must report the current observation without promising memory reservation.
- The SDK is imported in an offline environment or with proxies configured; no connection must be initiated.
- A heavyweight inference backend is installed in the environment; importing the foundation must not load it implicitly.
- The diagnostic runs on a Python version outside the supported range.
- Diagnostic output is redirected to a file or used in a terminal without advanced visual capabilities; the required content must remain readable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The product MUST be installable from the repository in editable mode and from a local artifact, without requiring publication to a public index.
- **FR-002**: The public identifiers MUST be `ceia-aisdk` for distribution and the command line, and `ceia_aisdk` for imports.
- **FR-003**: The installation MUST declare support for Python 3.11, 3.12, and 3.13 on Linux x86_64 and MUST NOT promise support for Windows or other architectures.
- **FR-004**: The base installation MUST reserve the optional `[cuda]` group and NEED NOT provide the `[server]` and `[apps]` groups in this feature.
- **FR-005**: The `ceia-aisdk` help MUST list `doctor`.
- **FR-006**: The same product version MUST be accessible through `ceia_aisdk.__version__` and the diagnostic.
- **FR-007**: The initial documentation MUST explain that this feature is installed from the repository, supports only Linux x86_64, and does not correspond to the public `0.1.0` release.
- **FR-008**: Importing `ceia_aisdk` MUST NOT load LLM, voice, vision, or compute-intensive backends.
- **FR-009**: Importing `ceia_aisdk` and running `doctor` MUST NOT initiate network connections.
- **FR-010**: The SDK MUST provide `AISDKConfig` with the public options `device`, `cache_dir`, `log_level`, and `offline`.
- **FR-011**: The configuration MUST resolve each option independently according to this precedence: explicit arguments, `CEIA_AISDK_*` variables, `~/.ceia-aisdk/config.toml`, and defaults.
- **FR-012**: The SDK MUST recognize, at minimum, `CEIA_AISDK_DEVICE`, `CEIA_AISDK_CACHE_DIR`, `CEIA_AISDK_LOG_LEVEL`, and `CEIA_AISDK_OFFLINE`.
- **FR-013**: In the absence of configuration, `cache_dir` MUST be the expanded path of `~/.ceia-aisdk`, `device` MUST be `auto`, `offline` MUST be false, and the process's initial level MUST be `WARNING`.
- **FR-014**: The absence of the local configuration file MUST NOT be treated as an error.
- **FR-015**: Invalid configuration values MUST be rejected with an actionable explanation; the complete contents of the configuration file MUST NOT be included in messages or logs.
- **FR-016**: The `offline` option MUST be loaded and exposed, but this feature MUST NOT implement downloads or blocking policies for future modules.
- **FR-017**: Logs emitted by the SDK MUST use the `ceia_aisdk.*` namespace.
- **FR-018**: The absence of a GPU during automatic selection MUST result in CPU and MUST NOT emit a log at `WARNING` level or higher.
- **FR-019**: Device resolution MUST return only `cpu`, `cuda`, or `cuda:N`.
- **FR-020**: When one or more NVIDIA GPUs are available in `auto` mode, selection MUST be deterministic and explicitly identify the selected index.
- **FR-021**: For each detected GPU, the SDK MUST provide its index, name, total memory, and free memory.
- **FR-022**: When CUDA is explicitly required and unavailable, the SDK MUST raise `DeviceError` with remediation indicating that the user should use CPU or fix the CUDA environment.
- **FR-023**: Device selection in this feature MUST NOT depend on a model's alias, size, or memory requirements.
- **FR-024**: All public failures in this feature MUST derive from `AISDKError` and expose `.remediation` as a nonempty string.
- **FR-025**: The `ceia-aisdk doctor` command MUST display the operating system, architecture, Python version, product version, selected device, detected GPUs, `cache_dir`, `offline`, and available optional groups.
- **FR-026**: The diagnostic MUST include a self-contained “copy this” block for attachment to issues.
- **FR-027**: The diagnostic MUST exit with code zero when the Python version is supported, the package is importable, and the device configuration is usable.
- **FR-028**: The diagnostic MUST exit with a nonzero code when the Python version is unsupported or when explicitly required CUDA cannot be used.
- **FR-029**: The diagnostic MUST NOT download models, require internet access, send telemetry, or transmit data.
- **FR-030**: The diagnostic and logs MUST NOT reveal user file contents.
- **FR-031**: This feature MUST NOT publish `ceia-aisdk` to the public index; distribution metadata may be prepared, and test-index trials do not count as a release.

### Scope Boundaries

Included in this feature:

- Local installation of the SDK foundation.
- Public contracts for version, configuration, device, errors, logs, and diagnostics.
- CPU and NVIDIA GPU detection on Linux x86_64.
- The minimum documentation and continuous verification necessary to demonstrate these contracts.

Explicitly excluded:

- Download, catalog, weight caching, and model-management commands.
- LLM, voice, vision, or RAG inference, or any selection based on model size.
- HTTP server, application launcher, and desktop packaging.
- Publication to public PyPI, binaries, installers, and weights within distribution artifacts.
- Catalog signatures, mirrors, transmitted telemetry, and metrics hooks.
- Windows, Apple Silicon, ROCm, and Vulkan.
- `LicenseError` and `CatalogSignatureError`.

### Key Entities

- **SDK Configuration**: Represents the effective device, cache directory, log level, and offline mode values, together with the precedence that determines each value.
- **Compute Device**: Represents a selectable CPU or CUDA index and its availability state.
- **Detected GPU**: Represents the observed index, name, total memory, and free memory of an NVIDIA GPU.
- **Diagnostic Report**: Aggregates the environment, product version, effective configuration, hardware, optional groups, and readiness result in a readable, copyable format.
- **Public SDK Error**: Represents a failure understandable to the user, with a mandatory message and remediation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a reference machine with a compatible Python version already installed, 95% of local installations completed in a clean environment finish within 60 seconds, and 100% allow the package to be imported and the command help to be opened on the first attempt.
- **SC-002**: The local artifact of the base library, without optional groups, adds at most 5 MB beyond the foundation's declared dependencies.
- **SC-003**: On reference SSD storage, 95% of `ceia_aisdk` imports complete within 200 ms without loading inference backends.
- **SC-004**: On Linux x86_64 without a GPU, 100% of `ceia-aisdk doctor` runs complete within 5 seconds with exit code zero and CPU as the device.
- **SC-005**: On a reference NVIDIA machine, the diagnostic reports the correct name and index, and total and free memory within 256 MB of the reference reading taken during the same test interval.
- **SC-006**: 100% of automated precedence cases across explicit arguments, environment variables, the local file, and defaults produce the expected value for each supported option.
- **SC-007**: Network tests observe zero connection attempts during import and diagnostics, including in an offline environment.
- **SC-008**: In an evaluation with at least five representative developers, at least 90% can determine on the first run whether the foundation is usable and copy the diagnostic block or follow the indicated remediation without consulting additional documentation.
- **SC-009**: 100% of public errors exercised in tests provide nonempty remediation, and no diagnostic report includes personal file contents.

## Assumptions

- The user starts with an intact clone of the repository and Python 3.11, 3.12, or 3.13 already available on Linux x86_64.
- Ubuntu 22.04 or later is the reference environment; other Linux x86_64 distributions may work, but do not expand this feature's mandatory matrix.
- In `auto` mode, the first usable NVIDIA GPU with the lowest index is selected; if none is available, CPU is the supported fallback.
- The free-memory value is an instantaneous observation and may vary; the accuracy comparison uses readings taken close together in time.
- The local file may specify `INFO`, but without effective explicit configuration, the process starts at `WARNING`.
- The `[cuda]` group may be only a documented reservation in this feature; functional CUDA inference is a PRD-02 gate.
- If recognized in advance, the telemetry flag remains disabled and has no network effect.
- The decisions ratified in the PRD program on 2026-09-01 and PRD-00 are the normative sources for this specification.
- The project constitution still contains placeholders and therefore adds no ratified principles to this specification.

### Dependencies

- Detailed GPU detection depends on the Linux environment exposing NVIDIA information locally; the absence or failure of this capability must preserve CPU operation when `device=auto`.
- PRD-00 does not depend on a registry, models, internet access, or an external service.
- PRD-01 and all subsequent modules depend on the public contracts established in this feature.
