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
