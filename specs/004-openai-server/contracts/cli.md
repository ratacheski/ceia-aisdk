# CLI Contract: `ceia-aisdk serve`

**Feature**: `004-openai-server`
**Console script**: `ceia-aisdk`
**Command**: `serve`

This contract amends
[001-sdk-foundations/contracts/cli.md](../../001-sdk-foundations/contracts/cli.md).
`doctor` and `model` remain unchanged except diagnostics extras in
[diagnostics.md](diagnostics.md).

## Root Command

`ceia-aisdk --help` MUST list `serve` with nonempty short help. Root examples MAY include
`ceia-aisdk serve --help`. The command tree still contains no app-launcher commands.

## Serve Command

### Invocation

```text
ceia-aisdk serve [OPTIONS]
```

### Options

| Option | Required | Default | Constraints |
|--------|----------|---------|-------------|
| `--host` | no | `127.0.0.1` | Bind address. Default MUST NOT be `0.0.0.0`. |
| `--port` | no | `11434` | Integer TCP port. |
| `--token` | no | unset | When set, require `Authorization: Bearer`. |
| `--cors` | no | off | Boolean flag. Relaxes CORS to any origin. |
| `--debug` | no | off | Boolean flag. DEBUG logs; MAY log message bodies. |

Help MUST warn that `--host 0.0.0.0` exposes the process beyond the machine, that TLS is
provided by a reverse proxy, and that the `[server]` extra is required to listen.

### Help contract

`ceia-aisdk serve --help` MUST:

- exit with code `0` even when the `[server]` extra is not installed;
- describe the purpose (OpenAI-compatible local server);
- document every option above, required status, and defaults;
- state Linux x86_64;
- mention opaque aliases and `/v1`;
- include at least one executable example.

Required example (must remain executable by the help harvester):

```text
ceia-aisdk serve --help
```

Documented start example (long-running; help-example tests MUST skip it):

```text
ceia-aisdk serve
```

### Missing extra

When FastAPI or uvicorn cannot be imported, `ceia-aisdk serve` (without `--help`) exits `1`,
prints `ServerError` message and remediation to stderr, and MUST NOT print a Python traceback.

### Successful start

- Binds `--host`:`--port`.
- Logs an absolute URL containing the host, port, and `/v1`.
- Does not log `messages` unless `--debug`.
- Remains in the foreground until SIGINT/SIGTERM.

### Bind failure

Exit `1`. Nonempty remediation mentions `--port` and stopping the occupant (for example another
local server on 11434). No hang and no silent port change.

### Exit codes

- `0`: help requested, or the process received an orderly shutdown after a successful bind
  (implementation MAY use 0 on SIGINT).
- `1`: missing extra, bind failure, or other `ServerError` / `AISDKError`.
- `2`: invalid CLI invocation (framework).

## Test Contract

Automated tests MUST verify:

- root help lists `serve`;
- `serve --help` completeness and English-only text;
- `serve --help` works in an environment without FastAPI (or the missing-extra path is unit
  tested by stubbing the import);
- missing extra start path explains `ceia-aisdk[server]`;
- executable-example harvesting skips long-running `serve` without `--help`.
