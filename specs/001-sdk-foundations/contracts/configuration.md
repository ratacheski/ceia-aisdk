# Configuration Contract: Operational Foundations

**Feature**: `001-sdk-foundations`
**Configuration file**: `~/.ceia-aisdk/config.toml`

## Effective Fields

### Device

- Public field: `device`
- Environment variable: `CEIA_AISDK_DEVICE`
- TOML key: `core.device`
- Default: `auto`
- Accepted values: `auto`, `cpu`, `cuda`, `cuda:N`
- `N` must be a canonical nonnegative decimal integer.

### Cache Directory

- Public field: `cache_dir`
- Environment variable: `CEIA_AISDK_CACHE_DIR`
- TOML key: `core.cache_dir`
- Default: `~/.ceia-aisdk`
- Accepted explicit values: nonempty string or path-like value without NUL
- Accepted environment and TOML values: nonempty string without NUL
- The effective value is expanded with `expanduser()` and returned as `pathlib.Path`.
- Loading configuration does not create the directory or require it to exist.

### Log Level

- Public field: `log_level`
- Environment variable: `CEIA_AISDK_LOG_LEVEL`
- TOML key: `core.log_level`
- Default: `WARNING`
- Accepted values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- Values are case-sensitive and are not trimmed or normalized.

### Offline Mode

- Public field: `offline`
- Environment variable: `CEIA_AISDK_OFFLINE`
- TOML key: `core.offline`
- Default: `false`
- Explicit and TOML values must be booleans.
- Environment values must be exactly `0` or `1`.
- PRD-00 stores the value but has no download behavior to suppress.

## Precedence

Each field is resolved separately in this exact order:

1. non-`None` explicit argument to `AISDKConfig.load`;
2. matching environment variable, including an empty string;
3. matching key in the TOML `[core]` section;
4. default.

The first present source wins and is then validated. A valid higher-priority value shields an
invalid lower-priority value. An empty environment value is present and therefore fails
validation rather than falling through.

## TOML Shape

```toml
[core]
device = "auto"
cache_dir = "~/.ceia-aisdk"
log_level = "WARNING"
offline = false
```

Rules:

- A missing file is equivalent to no TOML values.
- An empty file is valid.
- Unknown sections and keys are ignored by PRD-00 for forward compatibility.
- A malformed or unreadable file raises `ConfigError`.
- Parsing never executes code, expands environment variables, or follows remote references.
- Errors may identify the path and failed field but must not include the complete file contents.

## Examples

### Defaults

```python
from ceia_aisdk import AISDKConfig

config = AISDKConfig.load()
```

Expected effective values:

```text
device=auto
cache_dir=~/.ceia-aisdk
log_level=WARNING
offline=false
```

The actual `cache_dir` object contains the expanded home path.

### Environment override

```bash
CEIA_AISDK_DEVICE=cpu \
CEIA_AISDK_CACHE_DIR=/tmp/ceia-cache \
CEIA_AISDK_LOG_LEVEL=INFO \
CEIA_AISDK_OFFLINE=1 \
uv run python -c "from ceia_aisdk import AISDKConfig; print(AISDKConfig.load())"
```

### Explicit override

Given environment value `CEIA_AISDK_DEVICE=cuda`, this call still selects the explicit
configuration value:

```python
config = AISDKConfig.load(device="cpu")
```

### Mixed sources

Fields do not share one winning source. An explicit `device`, environment `offline`, TOML
`cache_dir`, and default `log_level` may all coexist in one effective snapshot.

## Error Contract

Invalid winning values raise `ConfigError` with:

- the affected field when known;
- the source category when safe;
- accepted values or expected type;
- a nonempty `.remediation` action.

Messages and logs must not include:

- complete environment values;
- complete TOML contents;
- contents of any other user file;
- unrelated environment variables;
- credentials or tokens.

## Logging Interaction

Loading configuration has no logging side effect beyond optional debug messages. It does not set
the root logger or add output handlers. The CLI applies the effective level only to the
`ceia_aisdk` namespace after configuration has loaded successfully.

## Acceptance Matrix

Automated tests must cover, for every field:

- default only;
- TOML overriding the default;
- environment overriding TOML;
- explicit argument overriding environment and TOML;
- mixed sources across fields;
- invalid winning values;
- invalid lower-priority values hidden by a valid higher-priority value;
- missing and empty TOML files;
- malformed and unreadable TOML files;
- empty environment strings;
- path expansion under a temporary home directory.
