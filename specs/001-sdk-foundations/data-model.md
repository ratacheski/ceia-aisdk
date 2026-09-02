# Data Model: CEIA AI SDK Operational Foundations

**Feature**: `001-sdk-foundations`
**Date**: 2026-09-01

This feature has no database. Its data model consists of immutable in-memory snapshots derived
from configuration, local platform metadata, and a bounded NVIDIA probe.

## 1. SDK Configuration

### Purpose

Represents the effective, validated configuration used by library and CLI operations.

### Public representation

`AISDKConfig` is an immutable, slotted value object.

### Fields

- `device: str`
  - Accepted values: `auto`, `cpu`, `cuda`, or `cuda:N`.
  - `N` is a canonical nonnegative decimal integer.
  - Default: `auto`.
- `cache_dir: pathlib.Path`
  - Expanded with `expanduser()`.
  - Need not exist and is not created by PRD-00.
  - Default: expanded `~/.ceia-aisdk`.
- `log_level: str`
  - Accepted values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
  - Default: `WARNING`.
- `offline: bool`
  - Records intent only; PRD-00 has no download subsystem to block.
  - Default: `False`.

### Source resolution

Each field is resolved independently:

1. non-`None` explicit argument;
2. matching `CEIA_AISDK_*` environment variable;
3. matching key in the TOML `[core]` section;
4. field default.

The selected value is validated after precedence resolution. Invalid lower-priority values do not
override a valid higher-priority value.

### Validation failures

Malformed or unreadable TOML and an invalid selected value produce `ConfigError`. Error data may
name the field and source but must not reproduce full file contents or sensitive raw values.

## 2. Public GPU Information

### Purpose

Represents the non-sensitive NVIDIA information available to SDK users and the diagnostic report.

### Public representation

`GPUInfo` is an immutable, slotted value object.

### Fields

- `index: int`
  - Nonnegative and unique within one snapshot.
  - Represents the `nvidia-smi`/NVML index in PRD-00.
- `name: str`
  - Nonempty display name.
- `total_vram_mib: int`
  - Nonnegative total memory in MiB.
- `free_vram_mib: int`
  - Current free memory in MiB.
  - Must satisfy `0 <= free_vram_mib <= total_vram_mib`.

### Privacy boundary

The public object and diagnostic output exclude GPU UUIDs, serial numbers, PCI bus identifiers,
and other stable machine identifiers.

## 3. Internal NVIDIA Probe Record

### Purpose

Carries fields needed to validate and select a GPU without exposing stable identifiers.

### Fields

- `index: int`
- `uuid: str`
- `name: str`
- `total_vram_mib: int`
- `free_vram_mib: int`
- `compute_mode: str`
- `mig_mode: str`
- `usable: bool`
  - True when compute mode is not prohibited and MIG mode does not require unsupported
    instance-level selection.

### Conversion

A valid internal record converts to `GPUInfo` by omitting UUID, compute mode, MIG mode, and the
derived usability flag.

## 4. Hardware Snapshot

### Purpose

Represents one bounded local hardware observation reused for both device selection and diagnostic
display.

### Fields

- `gpus: tuple[GPUInfo, ...]`
  - Sorted by numeric index.
- `usable_gpu_indices: tuple[int, ...]`
  - Sorted subset of detected GPU indices.
- `probe_status: ProbeStatus`
  - `not_run`, `succeeded`, or `failed`.
- `probe_detail: str | None`
  - Privacy-safe diagnostic reason for a failed probe.
  - Never contains arbitrary command output.

### Invariants

- `not_run` has no GPUs and no probe detail.
- `succeeded` may contain zero or more GPUs and has no failure detail.
- `failed` has no trusted GPU records and contains a bounded, sanitized detail.
- A single snapshot is used for selection and output to prevent contradictory readings.

## 5. Device Selection

### Purpose

Captures the relationship between the requested device, hardware snapshot, and effective device.

### Fields

- `requested: str`
  - Validated configuration value.
- `effective: str`
  - `cpu` or `cuda:N`.
- `selected_gpu: GPUInfo | None`
  - Present only when `effective` is CUDA.

### Rules

- `cpu` produces `cpu` without running the NVIDIA probe.
- `auto` selects the lowest usable GPU index, otherwise `cpu`.
- `cuda` selects the lowest usable GPU index, otherwise raises `DeviceError`.
- `cuda:N` selects exactly `N`, otherwise raises `DeviceError`.
- Probe failure is a supported CPU fallback only for `auto`.
- Device selection does not inspect aliases, model size, or future inference backends.

## 6. Diagnostic Check

### Purpose

Represents one machine-readiness observation in a stable, testable form.

### Fields

- `key: str`
  - Stable internal identifier.
- `label: str`
  - English display label.
- `status: CheckStatus`
  - `pass`, `info`, or `fail`.
- `summary: str`
  - Bounded, privacy-safe value or explanation.
- `remediation: str | None`
  - Required when status is `fail`.

### Invariants

- A failed check always has nonempty remediation.
- Summaries exclude file contents and stable host identifiers.
- Check order is deterministic.

## 7. Diagnostic Report

### Purpose

Aggregates all information needed by interactive output, plain output, the copyable block, and
the process exit decision.

### Fields

- `operating_system: str`
- `architecture: str`
- `python_version: str`
- `python_supported: bool`
- `package_version: str`
- `package_importable: bool`
- `configured_device: str`
- `effective_device: str | None`
- `gpus: tuple[GPUInfo, ...]`
- `cache_dir: str`
  - Home-relative paths are normalized to `~`.
- `offline: bool`
- `optional_groups: tuple[str, ...]`
  - PRD-00 reports CUDA as reserved and does not claim runtime installation.
- `checks: tuple[DiagnosticCheck, ...]`
- `usable: bool`
- `exit_code: int`

### Invariants

- `usable=True` implies supported Python, importable package, and successful device selection.
- `usable=True` maps to exit code `0`.
- `usable=False` maps to exit code `1`.
- The report excludes hostname, username, IP addresses, current working directory, raw
  environment contents, file contents, UUIDs, and serial numbers.
- Interactive and plain renderers consume the same report and cannot change its outcome.

## 8. Public SDK Error

### Purpose

Defines the stable failure contract shared by configuration, hardware, CLI, and future modules.

### Public hierarchy

- `AISDKError`
  - Root public exception.
- `ConfigError`
  - Invalid or unreadable effective configuration.
- `DeviceError`
  - Explicitly requested device cannot be selected.

### Fields

- `message: str`
  - Nonempty, user-facing English explanation.
- `remediation: str`
  - Nonempty, user-facing English next action.

### Invariants

- Public error construction rejects empty message or remediation.
- String rendering includes the message; callers can access remediation separately.
- Native exceptions may be chained for maintainers but their raw text is not automatically
  exposed in diagnostic output.

## State Transitions

### Configuration

```text
unloaded
  -> sources read
  -> each field resolved
  -> all winners valid -> immutable AISDKConfig
  -> any winner invalid -> ConfigError
```

### Hardware and device

```text
requested cpu
  -> no probe -> effective cpu

requested auto
  -> probe succeeds with usable GPU -> effective cuda:N
  -> no usable GPU or probe fails -> effective cpu

requested cuda or cuda:N
  -> requested target usable -> effective cuda:N
  -> target unavailable or probe fails -> DeviceError
```

### Diagnostic

```text
collect configuration and platform facts
  -> collect one hardware snapshot when needed
  -> evaluate deterministic checks
  -> usable -> render report and exit 0
  -> unusable -> render report with remediation and exit 1
```
