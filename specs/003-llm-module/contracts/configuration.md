# Configuration Contract: LLM Settings

**Feature**: `003-llm-module`
**Configuration file**: `~/.ceia-aisdk/config.toml`

This contract adds the `[llm]` table. The `[core]` table and `AISDKConfig` public fields from
[001-sdk-foundations/contracts/configuration.md](../../001-sdk-foundations/contracts/configuration.md)
are unchanged.

## Effective Fields

### Default Alias

- Public field: `LLMSettings.default_alias`
- Environment variable: `CEIA_AISDK_LLM_DEFAULT_ALIAS`
- TOML key: `llm.default_alias`
- Default: `llm/small@latest`
- Accepted values: cataloged alias forms, including unqualified sizes that the LLM module
  interprets with `domain="llm"` (for example `medium` → `llm/medium`).
- Constructor `LLM(alias)` is not a settings-load field; it wins over this value.

### Context Length

- Public field: `LLMSettings.context_length`
- Environment variable: `CEIA_AISDK_LLM_CONTEXT_LENGTH`
- TOML key: `llm.context_length`
- Default: `8192`
- Accepted values: positive integers. Environment values are canonical base-10 integers
  without a sign prefix other than a single optional `+`.
- Effective backend context is `min(context_length, PublicModelMetadata.context_length)`.

## Precedence

Each `[llm]` field is resolved independently:

1. non-`None` explicit argument to `LLMSettings.load` or the matching `LLM` constructor
   argument;
2. matching `CEIA_AISDK_LLM_*` variable, including an empty string (empty fails validation);
3. matching key in the TOML `[llm]` section;
4. default.

`AISDKConfig.device` remains the device source unless `LLM(..., device=)` is passed.

## TOML Shape

```toml
[core]
device = "auto"
cache_dir = "~/.ceia-aisdk"
log_level = "WARNING"
offline = false

[llm]
default_alias = "llm/small@latest"
context_length = 8192
```

Rules:

- A missing `[llm]` table is equivalent to defaults.
- Unknown keys in `[llm]` are ignored for forward compatibility.
- Invalid winning values raise `ConfigError` with nonempty remediation and MUST NOT dump the
  entire file.

## Constructor Override Examples

```python
LLM()                       # llm/small@latest
LLM("medium")                # llm/medium@latest (or pinned latest)
LLM("llm/small@1")           # explicit version
LLM(device="cpu")            # force CPU
```

Given TOML `default_alias = "medium"`, `LLM()` uses medium and `LLM("llm/small")` still uses
small.
