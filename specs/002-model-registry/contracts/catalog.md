# Catalog Contract: Model Registry

**Feature**: `002-model-registry`
**Bundled file**: `ceia_aisdk/registry/_internal_catalog.yaml` (not a public API)
**Override**: environment variable `CEIA_AISDK_CATALOG`

## Active Catalog Selection

1. If `CEIA_AISDK_CATALOG` is unset or empty, use the bundled package data file.
2. If the value is an existing local path, read that YAML file.
3. If the value is an `http://` or `https://` URL, fetch it once per process load (not on an
   interval, and not when `AISDKConfig.offline` is true).
4. There is no merge with the bundled catalog and no fallback to a public organization.

A remote override is unsigned. Documentation and `model info --help` must state that
authenticity is not verified and that integrity applies to artifact checksums.

## Document Schema (`schema_version: 1`)

```yaml
schema_version: 1
essentials:
  - llm/small
models:
  llm:
    small:
      latest: 1
      versions:
        1:
          url: "https://models.example.invalid/llm-small-v1.bin"
          sha256: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
          size_bytes: 16777216
          public:
            license_family: apache-2.0
            commercial_use: true
            context_length: 8192
            size_gb: 0.02
            capabilities:
              - chat
            quantization_class: compact
```

The compact example above is the shape used by local test catalogs. The bundled production
document pins the published v1 artifacts below. Automated tests MUST override it and MUST NOT
download these files.

## Bundled production catalog (v1, 2026-09-01)

Organization: `ceia-aisdk`. Each repository stores a single opaque file `model.gguf`.
`model info` and public exceptions still MUST NOT print these URLs.

| Alias          | Repository                 | SHA-256                                                            | Bytes      | size_gb |
| -------------- | -------------------------- | ------------------------------------------------------------------ | ---------- | ------- |
| `llm/small@1`  | `ceia-aisdk/llm-small-v1`  | `2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e` | 2497280736 | 2.33    |
| `llm/medium@1` | `ceia-aisdk/llm-medium-v1` | `65b8fcd92af6b4fefa935c625d1ac27ea29dcb6ee14589c55a8f115ceaaa1423` | 4683074240 | 4.36    |
| `llm/large@1`  | `ceia-aisdk/llm-large-v1`  | `e47ad95dad6ff848b431053b375adb5d39321290ea2c638682577dafca87c008` | 8988110976 | 8.37    |

Provenance (not public SDK metadata): Q4_K_M GGUF redistributions of
`Qwen/Qwen3-4B-Instruct-2507`, `Qwen/Qwen2.5-7B-Instruct`, and `Qwen/Qwen2.5-14B-Instruct`.
License family `apache-2.0`, `commercial_use: true`, `context_length: 32768`,
`quantization_class: standard`, capabilities `chat`, `tool_use`, `multilingual`.

Download URL pattern:

```text
https://huggingface.co/ceia-aisdk/llm-<size>-v1/resolve/main/model.gguf
```

`essentials` in the bundled document is `[llm/small]` only.

### Required rules

- `schema_version` is the integer `1`.
- `essentials` is a list of fully qualified aliases (`domain/size`). Unknown names warn at
  `--essentials` time.
- Each `models.<domain>.<size>.latest` is a positive integer that exists under `versions`.
- Each version has exactly one `url` (`http` or `https`), one SHA-256 (64 lowercase hex
  characters), positive `size_bytes`, and a complete `public` block.
- `quantization_class` is `compact`, `standard`, or `high-quality`.
- `commercial_use` is a boolean.
- `capabilities` is a nonempty list of strings.
- Mirror lists, signature fields, and extra download URLs are rejected as invalid schema.

### Resolution

| Input                 | Result                                      |
| --------------------- | ------------------------------------------- |
| `llm/small`           | `llm/small@<latest>`                        |
| `llm/small@latest`    | same pin as `llm/small`                     |
| `llm/small@1`         | version `1` if present                      |
| CLI `small`           | `llm/small` then latest pin                 |
| missing name          | `ModelNotFoundError` plus same-domain names |

`@latest` does not contact a remote catalog index. Changing latest requires a new catalog
document (SDK upgrade or override).

## Package Data

- The YAML file is included in wheel and sdist.
- Weight files (`.gguf`, `.bin` model payloads, `.onnx`, and similar) must not appear in
  distribution artifacts.
- The module path `_internal_catalog` / `_internal_catalog.yaml` is not a supported import
  surface.

## Security

- Alias tokens and catalog URLs must not cause writes outside `<cache_dir>/models` or
  `<cache_dir>/models/.tmp`.
- Local override paths are read as data; they are not executed.
- Schema failures raise `DownloadError` with remediation that names this schema.
