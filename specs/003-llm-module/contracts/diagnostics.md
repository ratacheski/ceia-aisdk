# Diagnostics Contract: Doctor CUDA Binding

**Feature**: `003-llm-module`
**Command**: `ceia-aisdk doctor` (no new subcommand)

This contract amends
[001-sdk-foundations/contracts/cli.md](../../001-sdk-foundations/contracts/cli.md)
for optional-group reporting and a CUDA inference-binding probe. All privacy, timeout, and
zero-network rules remain in force except the backend-import rule below.

## Binding Probe (amendment)

`doctor` MAY import `llama_cpp` **in the CLI process only** to answer whether the installed
binding supports GPU offload. It MUST NOT:

- construct a model;
- read cache files or GGUF weights;
- download anything;
- import `llama_cpp` from `ceia_aisdk.__init__`.

If `llama_cpp` is missing or the import fails, `cuda_binding` is `no` and the foundation remains
usable on CPU (`exit_code=0` when other checks pass).

The CPU-only 5-second budget still applies. The probe must be a metadata/capability read, not a
generation.

## Copyable Block Additions

Insert `cuda_binding` after `offline` and replace the reserved extra token:

```text
offline=<true|false|unavailable>
cuda_binding=<yes|no>
optional_groups=<cuda|none>
```

`optional_groups=cuda` when the installed distribution declares the extra, even if the extra is
not installed in the current environment. Implementations MAY append other extras later. The
literal `cuda:reserved` MUST NOT appear after this feature.

## Help Text

`ceia-aisdk doctor --help` MUST mention that the command reports whether the CUDA inference
binding is present, distinct from whether a GPU is visible.

## Interactive and Plain Output

Both renderers show:

- GPU summary (existing);
- `cuda_binding` yes/no;
- optional groups without the “reserved and empty” PRD-00 wording.

## Test Contract Additions

Automated tests MUST verify:

- `import ceia_aisdk` still does not load `llama_cpp`;
- doctor copy-block keys include `cuda_binding` in the specified order;
- mocked missing `llama_cpp` yields `cuda_binding=no` and a usable CPU report;
- doctor still completes within 5 seconds on the CPU-only reference path and opens zero
  sockets.
