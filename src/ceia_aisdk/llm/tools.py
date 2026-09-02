"""Tool declaration types for optional LLM tool use."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolDeclaration:
    """OpenAI-ish tool schema accepted by ``LLM`` and ``AsyncLLM``.

    Attributes:
        name: Nonempty unique tool name.
        description: English description shown to the model.
        parameters: JSON Schema object for the tool arguments.
        handler: Optional local callable invoked for a tool call loop.
    """

    name: str
    description: str
    parameters: Mapping[str, object]
    handler: Callable[..., object] | None = None


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One model-requested function call from a single generate step.

    Attributes:
        id: Client-echoed identifier used as ``tool_call_id`` on the next
            ``role: tool`` message.
        name: Function name from the tool schema.
        arguments: JSON object encoded as a string (OpenAI wire form).
    """

    id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class CompletionResult:
    """Outcome of one ``complete`` generate step.

    A successful result has nonempty ``content`` or nonempty ``tool_calls``.

    Attributes:
        content: Assistant text when the model did not request tools.
        tool_calls: Structured calls when the model requested tools.
    """

    content: str | None = None
    tool_calls: tuple[ToolCall, ...] | None = None
