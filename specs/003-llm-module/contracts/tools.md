# Tools Contract: LLM Tool Use (P1)

**Feature**: `003-llm-module`
**Priority**: P1 — MUST NOT block first-chat or the `0.1.0` upload

**Superseded in part by** [004-openai-server/contracts/tools.md](../../004-openai-server/contracts/tools.md):
`0.2.0` adds `LLM.complete` / `CompletionResult` / OpenAI `tool_calls` on `/v1/chat/completions`.
This 003 file remains the `ToolDeclaration` and capability-gate contract for `0.1.0`.

This contract exists so PRD-06 can expose the same convention. Implementation MAY ship in
`0.1.0` or the first patch.

## Public Shape

```python
@dataclass(frozen=True, slots=True)
class ToolDeclaration:
    name: str
    description: str
    parameters: Mapping[str, object]
    handler: Callable[..., object] | None = None
```

`parameters` is a JSON Schema object (`type`/`properties`/`required` as needed).

Passing `tools=[...]` into `LLM` / `AsyncLLM` / session send is the OpenAI-ish calling
convention: the model may emit a named call; the SDK invokes `handler` when present and feeds
the result back for a bounded number of rounds.

## Capability Gate

If `get_public_metadata(alias).capabilities` does not contain `tool_use`, any nonempty `tools`
argument raises `CapabilityError` with remediation to choose an alias that lists `tool_use`
(for example cataloged `llm/medium` when it declares the capability).

Tools MUST NOT be silently ignored.

## Testing

- Unit tests cover the capability gate without a real model.
- One loop demonstration (`get_weather` stub) uses a capable catalog alias, a recording, or an
  explicit skip when the CI GGUF cannot call tools. The skip message MUST be English and
  explicit.
- This test MUST NOT be on the critical path of the first-chat merge.

## Non-Goals

- Hosting an HTTP tools protocol (PRD-06).
- Guaranteeing that `llm/small` always calls tools in CI.
