# Tools Contract: Library One-Step Completion and Chat Completions

**Feature**: `004-openai-server`
**Amends**: [003-llm-module/contracts/tools.md](../../003-llm-module/contracts/tools.md)

PRD-02 introduced `ToolDeclaration` and a `tool_use` capability gate. Generation still returns
only `str`. This feature completes the missing step so `/v1/chat/completions` can speak OpenAI
`tools` / `tool_calls` on the same route. There is no `/v1/tools` endpoint.

## Library

`LLM.chat`, `LLM.stream`, and `Session.send` MUST keep their `0.1.0` signatures and return
`str` / `Iterator[str]`.

Add public types in `ceia_aisdk.llm` (exported from the module, not from `ceia_aisdk`):

```python
@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON object as a string

@dataclass(frozen=True, slots=True)
class CompletionResult:
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] | None = None
```

A successful result has either nonempty `content` or nonempty `tool_calls`, not both required.

```python
class LLM:
    def complete(
        self,
        messages: Sequence[Mapping[str, object]],
        *,
        tools: Sequence[ToolDeclaration] | None = None,
        tool_choice: str | Mapping[str, object] | None = None,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> CompletionResult: ...
```

`AsyncLLM` MUST mirror `complete` as `async` when that class is present.

Contract:

- `messages` use roles `system`, `user`, `assistant`, `tool`.
- Assistant messages MAY include `tool_calls`. Tool messages MUST include `tool_call_id`.
- Nonempty `tools` on an alias whose public capabilities lack `tool_use` raises
  `CapabilityError` (same remediation as 003). Tools MUST NOT be silently ignored.
- `complete` performs **one** generate. It MUST NOT run `ToolDeclaration.handler` and MUST NOT
  loop. Optional handler loops remain a later or separate library convenience and are not
  required for `0.2.0`.
- Importing `ceia_aisdk.llm` still MUST NOT load `llama_cpp`.

## HTTP

`POST /v1/chat/completions` maps OpenAI `tools` / `tool_choice` / `messages` onto `complete`.

When `CompletionResult.tool_calls` is set:

```json
{
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_...",
            "type": "function",
            "function": {"name": "get_weather", "arguments": "{\"city\":\"Lisbon\"}"}
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ]
}
```

The client executes the function and sends a new POST that includes the assistant tool-call
message and `{"role": "tool", "tool_call_id": "call_...", "content": "..."}`.

`stream: true` emits OpenAI `delta.tool_calls` and ends with `data: [DONE]`.

`GET /v1/models` MUST NOT claim tool calling for aliases without catalog `tool_use`.

The serve process MUST NOT invoke handlers.

## Testing

- Unit: fake backend returns `CompletionResult` with tool calls; capability gate still raises;
  `LLM.chat` still returns `str`.
- HTTP: fake or recording proves the JSON shape, a `role: tool` follow-up, SSE tool deltas,
  and 400 when the alias lacks `tool_use`.
- Tiny CI GGUF MAY skip a live `get_weather` emit; the skip or recording MUST be explicit and
  English. A live capable alias remains a reference-machine checklist item.

## Non-Goals

- A dedicated tools URL.
- Server-side tool execution.
- Vision image parts (still 400).
- Changing `LLM.chat` to a union type.
