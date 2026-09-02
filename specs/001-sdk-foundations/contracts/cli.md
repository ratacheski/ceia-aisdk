# CLI Contract: Operational Foundations

**Feature**: `001-sdk-foundations`
**Console script**: `ceia-aisdk`

## Root Command

### Invocation

```text
ceia-aisdk [OPTIONS] COMMAND [ARGS]...
```

### Required behavior

- `ceia-aisdk --help` exits with code `0`.
- Root help includes the SDK purpose, supported platform, available commands, and an Examples
  section.
- Root help lists `doctor` with nonempty short help.
- The command tree contains no model, inference, server, application, or publication commands in
  PRD-00.

### Required example

```text
ceia-aisdk doctor
```

## Doctor Command

### Invocation

```text
ceia-aisdk doctor
```

PRD-00 defines no feature-specific arguments or options for `doctor`; framework-provided help is
allowed.

### Help contract

`ceia-aisdk doctor --help` must:

- exit with code `0`;
- explain that it inspects the local foundation without downloading or transmitting data;
- describe the supported Linux x86_64 scope;
- state that CUDA forced by configuration can make the command fail;
- include examples for default execution and a CPU-forced execution.

Required examples:

```text
ceia-aisdk doctor
CEIA_AISDK_DEVICE=cpu ceia-aisdk doctor
```

## Diagnostic Content

The semantic report contains these fields in deterministic order:

1. overall status;
2. operating system;
3. architecture;
4. Python version and support status;
5. SDK version and importability;
6. configured device;
7. effective device or unavailability;
8. zero or more GPUs with index, name, total MiB, and free MiB;
9. normalized cache directory;
10. offline state;
11. available optional groups, with CUDA marked as reserved in PRD-00;
12. individual readiness checks;
13. remediation for each failed check;
14. process exit code.

## Output Modes

### Interactive terminal

- Rich formatting may use color, borders, and responsive wrapping.
- Every required semantic field remains visible.
- Formatting must remain readable at 80- and 120-column widths.

### Redirected or noninteractive stream

- Output is deterministic plain text.
- No ANSI escape sequence is emitted.
- Field and check ordering matches the semantic report.
- `TERM=dumb` and `NO_COLOR` produce readable output.

### Copyable block

Every execution, including an unusable result, includes a fixed-order ASCII block:

```text
--- CEIA AI SDK doctor: copy this ---
status=<usable|unusable>
os=<operating-system>
architecture=<architecture>
python=<version>
python_supported=<true|false>
sdk_version=<version>
sdk_importable=<true|false>
configured_device=<value>
effective_device=<cpu|cuda:N|unavailable>
gpus=<none|summary>
cache_dir=<normalized-path|unavailable>
offline=<true|false|unavailable>
optional_groups=cuda:reserved
checks=<pass-count>/<total-count>
exit_code=<0|1>
remediation=<none|sanitized-summary>
--- end CEIA AI SDK doctor ---
```

Contract:

- The block does not wrap and contains no ANSI sequences.
- Values are single-line and control characters are removed.
- Multiple GPUs use a bounded semicolon-separated summary.
- A home-directory prefix is normalized to `~`.
- Remediation is concise and contains no native stack trace.

## Privacy Contract

Neither formatted output nor the copyable block may contain:

- hostname;
- username;
- IP or MAC address;
- GPU UUID, serial number, or PCI bus identifier;
- current working directory;
- complete environment variables;
- TOML contents;
- arbitrary user-file contents;
- telemetry or persistent host identifiers.

Unexpected native exceptions are translated to a bounded internal-failure check. Raw command
stdout/stderr and stack traces are not included in the report.

## Exit Codes

- `0`: help was requested, or `doctor` determined that the foundation is usable.
- `1`: `doctor` completed but the Python/package/device foundation is unusable.
- `2`: invalid CLI invocation, reserved by the CLI framework.

A missing GPU in `device=auto` is usable and exits `0` with CPU selected. Explicit unavailable
`cuda` or `cuda:N` exits `1` and includes `DeviceError.remediation`.

## Performance and Side-Effect Contract

`doctor` must:

- complete within 5 seconds on the reference CPU-only system;
- apply a 2-second maximum to the NVIDIA subprocess;
- perform no DNS, socket, HTTP, model, catalog, or telemetry operation;
- avoid creating the cache or configuration directory;
- avoid importing inference backends.

## Test Contract

Automated tests must verify:

- root and recursive subcommand help completeness;
- presence and executability of every documented example;
- exit codes and stdout/stderr separation;
- semantic equivalence between interactive and plain output;
- exact copyable-block keys and order;
- privacy exclusions;
- CPU-only, mocked single-GPU, mocked multi-GPU, probe-failure, and forced-CUDA cases;
- redirected output, `TERM=dumb`, `NO_COLOR`, and representative terminal widths;
- real installed console entry point from built wheel and source distribution;
- external 5-second timeout and zero network attempts.
