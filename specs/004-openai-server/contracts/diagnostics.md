# Diagnostics Contract: Server Extra Visibility

**Feature**: `004-openai-server`
**Command**: `ceia-aisdk doctor` (no new diagnostic subcommand)

This contract amends
[003-llm-module/contracts/diagnostics.md](../../003-llm-module/contracts/diagnostics.md).
Privacy, 5-second CPU budget, and zero-network rules remain in force. `doctor` MUST NOT import
FastAPI, MUST NOT bind a port, and MUST NOT load `llama_cpp` except for the existing CUDA
binding probe in the CLI process.

## Optional Groups

`optional_groups` MUST list extras **declared** by the installed distribution metadata
(`Provides-Extra`), in a stable order. After this feature that includes `cuda` and `server`.

Copyable block example:

```text
optional_groups=cuda,server
```

The literal `server:reserved` MUST NOT appear. An extra MAY be listed as declared even when it
is not installed in the current environment (same rule as CUDA in PRD-02).

When `[server]` is installed, doctor MAY additionally show that the extra is present via the
same `optional_groups` list; it MUST NOT start `serve`.

## Help Text

No doctor help change is required beyond remaining accurate. Serve-specific documentation lives
on `ceia-aisdk serve --help` and the README.

## Test Contract Additions

- `optional_groups` copy-block contains `server` after the extra is declared in metadata.
- `import ceia_aisdk` still does not import FastAPI or uvicorn.
- Doctor still completes within 5 seconds on the CPU-only path and opens zero sockets.
