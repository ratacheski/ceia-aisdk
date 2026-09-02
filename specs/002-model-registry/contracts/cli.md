# CLI Contract: Model Registry

**Feature**: `002-model-registry`
**Console script**: `ceia-aisdk`

This contract extends [001-sdk-foundations/contracts/cli.md](../../001-sdk-foundations/contracts/cli.md).
`doctor` behavior is unchanged. Root help must now also list `model`.

## Root Command

### Required additions

- `ceia-aisdk --help` lists `model` with nonempty short help.
- Root Examples include `ceia-aisdk model --help` in addition to existing `doctor` examples.
- All help text remains English.

## Model Group

### Invocation

```text
ceia-aisdk model [OPTIONS] COMMAND [ARGS]...
```

`ceia-aisdk model --help` exits `0`, describes opaque alias management, and lists `pull`,
`list`, `rm`, `info`, `verify`, and `where`.

Required example:

```text
ceia-aisdk model pull llm/small
```

### Alias arguments

Commands that take `ALIAS` accept:

- `llm/small`
- `llm/small@N`
- `llm/small@latest`
- unqualified `small` (resolved as `llm/small`)
- `hf://...` on `pull` (bypass)
- an existing filesystem path on `pull` (bypass)

## Pull

### Invocation

```text
ceia-aisdk model pull ALIAS
ceia-aisdk model pull --essentials
```

`--essentials` and `ALIAS` are mutually exclusive.

### Behavior

- Downloads a missing or corrupt cataloged artifact with progress on a TTY.
- Reuses a valid cache without starting a network download.
- `--essentials` pulls every essential alias present in the active catalog (`llm/small` at
  minimum in the bundled catalog). Missing essential names print a warning to stderr and do not
  crash.
- Offline cache miss exits `1` with `DownloadError` remediation within 100 ms.

### Help contract

`ceia-aisdk model pull --help` must:

- describe integrity checking and resume;
- mention `--essentials`;
- state that models are stored in the configured cache, not in the package;
- include examples:

```text
ceia-aisdk model pull llm/small
ceia-aisdk model pull --essentials
```

## List

### Invocation

```text
ceia-aisdk model list
```

Prints cached aliases and sizes. An empty cache is success with a readable empty-state message.

Required example:

```text
ceia-aisdk model list
```

## Remove

### Invocation

```text
ceia-aisdk model rm ALIAS
```

Deletes the cached file, sidecar, lock, and leftover partial for that alias. An uncached
cataloged alias exits `1` with remediation suggesting `model pull`. Unknown aliases are
`ModelNotFoundError`. Unrelated files are not deleted.

Required example:

```text
ceia-aisdk model rm llm/small
```

## Info

### Invocation

```text
ceia-aisdk model info ALIAS
```

Prints only public metadata for a cataloged alias: `license_family`, `commercial_use`,
`context_length`, `size_gb`, `capabilities`, `quantization_class`. May also print the canonical
`domain/size@N` identity. Must not print URL, SHA-256, repository, or upstream filename.

### Help contract

`ceia-aisdk model info --help` must state that catalog authenticity is not verified in this
increment and that integrity is the artifact checksum.

Required example:

```text
ceia-aisdk model info llm/small
```

## Verify

### Invocation

```text
ceia-aisdk model verify
```

Rehashes cached cataloged artifacts against the catalog. Empty cache exits `0`. Any mismatch
exits `1` and does not promote corrupt data.

Required example:

```text
ceia-aisdk model verify
```

## Where

### Invocation

```text
ceia-aisdk model where ALIAS
```

Prints the absolute cache path. Uncached aliases exit `1` with remediation to pull.

Required example:

```text
ceia-aisdk model where llm/small
```

## Output Modes

- Interactive TTY: Rich progress during downloads; readable tables/lists.
- Redirected or `TERM=dumb` / `NO_COLOR`: no ANSI required; commands still succeed; progress may
  degrade to a single status line.
- `info` and exception text for cataloged aliases contain none of: `huggingface.co`, a
  production repository path, an upstream GGUF filename, or the catalog URL.

## Exit Codes

- `0`: help, successful pull/list/rm/info/where, or successful verify.
- `1`: `ModelNotFoundError`, `DownloadError`, verify mismatch, or other `AISDKError`.
- `2`: invalid invocation, reserved by Typer.

Stderr for failures prints `str(error)` and `.remediation` without a native traceback.

## Side-Effect Contract

- `doctor` still performs no catalog or download operation.
- `model` commands create cache directories only when a write is required.
- Offline misses open no sockets.
- Weights are never written into the source tree or distribution artifacts.

## Test Contract

Automated tests must verify:

- root help lists `model` and `doctor`;
- recursive help completeness and executable examples for every `model` command;
- English-only help;
- `info` opacity snapshots;
- `pull --essentials` warning path;
- noninteractive pull completion without requiring a TTY.
