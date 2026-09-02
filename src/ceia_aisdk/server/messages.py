"""Translate OpenAI chat and tools payloads onto library completion inputs.

Vision image parts are rejected. Tools are forwarded only when the alias
declares ``tool_use``. The server never executes tool handlers.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


class RequestValidationFailure(Exception):
    """Raised when an OpenAI chat request cannot be translated."""

    def __init__(
        self,
        message: str,
        *,
        remediation: str,
        status_code: int = 400,
        error_type: str = "invalid_request_error",
    ) -> None:
        """Store a request-validation failure.

        Args:
            message: English explanation without a traceback.
            remediation: Nonempty next action.
            status_code: HTTP status to return.
            error_type: Machine-readable error type.
        """
        super().__init__(message)
        self.remediation = remediation
        self.status_code = status_code
        self.error_type = error_type


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """Validated OpenAI chat completion request.

    Attributes:
        model: Opaque alias from the client.
        messages: Role/content mappings safe for library generation.
        stream: Whether the client requested SSE.
        temperature: Sampling temperature. Default ``0.8``.
        max_tokens: Maximum tokens to generate. Default ``512``.
        seed: Optional generation seed.
        tools: Optional OpenAI tool declarations.
        tool_choice: Optional OpenAI tool-choice value.
    """

    model: str
    messages: list[dict[str, Any]]
    stream: bool = False
    temperature: float = 0.8
    max_tokens: int = 512
    seed: int | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any = None


def parse_chat_request(payload: Mapping[str, Any]) -> ChatRequest:
    """Parse and validate an OpenAI ``/v1/chat/completions`` body.

    Args:
        payload: JSON object from the client.

    Returns:
        A validated chat request with library defaults applied.

    Raises:
        RequestValidationFailure: If required fields are missing, ``n`` is not
            ``1``, or vision image parts are present.
    """
    model = payload.get("model")
    if not isinstance(model, str) or not model.strip():
        raise RequestValidationFailure(
            "The request must include a nonempty model alias.",
            remediation="Set model to an opaque alias such as llm/small.",
        )
    raw_messages = payload.get("messages")
    if not isinstance(raw_messages, list) or not raw_messages:
        raise RequestValidationFailure(
            "The request must include a nonempty messages array.",
            remediation="Send at least one chat message with a role and content.",
        )
    n_value = payload.get("n", 1)
    if n_value != 1:
        raise RequestValidationFailure(
            "Only n=1 is supported.",
            remediation="Omit n or set n to 1.",
        )
    messages = [_translate_message(item, index) for index, item in enumerate(raw_messages)]
    temperature = _optional_float(payload.get("temperature"), default=0.8, name="temperature")
    max_tokens = _optional_int(payload.get("max_tokens"), default=512, name="max_tokens")
    seed = payload.get("seed")
    if seed is not None and not isinstance(seed, int):
        raise RequestValidationFailure(
            "seed must be an integer when provided.",
            remediation="Pass an integer seed or omit the field.",
        )
    tools = payload.get("tools")
    if tools is not None and not isinstance(tools, list):
        raise RequestValidationFailure(
            "tools must be an array when provided.",
            remediation="Pass an OpenAI tools array or omit the field.",
        )
    return ChatRequest(
        model=model.strip(),
        messages=messages,
        stream=bool(payload.get("stream", False)),
        temperature=temperature,
        max_tokens=max_tokens,
        seed=seed,
        tools=list(tools) if isinstance(tools, list) else None,
        tool_choice=payload.get("tool_choice"),
    )


def is_single_user_text(messages: Sequence[Mapping[str, Any]]) -> bool:
    """Return whether messages are one user string, matching ``LLM.chat``.

    Args:
        messages: Translated chat messages.

    Returns:
        True when the request is a single user text turn.
    """
    return (
        len(messages) == 1
        and messages[0].get("role") == "user"
        and isinstance(messages[0].get("content"), str)
    )


def tool_declarations_from_openai(tools: Sequence[Mapping[str, Any]] | None) -> list[Any]:
    """Map OpenAI ``tools`` onto library ``ToolDeclaration`` values.

    Args:
        tools: OpenAI tool objects, or ``None``.

    Returns:
        Library declarations without handlers. The server never executes them.

    Raises:
        RequestValidationFailure: If a tool object is missing a function name.
    """
    from ceia_aisdk.llm.tools import ToolDeclaration

    if not tools:
        return []
    declarations: list[ToolDeclaration] = []
    for item in tools:
        function = item.get("function", item) if isinstance(item, Mapping) else {}
        if not isinstance(function, Mapping):
            raise RequestValidationFailure(
                "Each tool must include a function object.",
                remediation="Send OpenAI function tools with a name and parameters.",
            )
        name = function.get("name")
        if not isinstance(name, str) or not name.strip():
            raise RequestValidationFailure(
                "Each tool function must have a nonempty name.",
                remediation="Set function.name on every tool.",
            )
        description = function.get("description", "")
        parameters = function.get("parameters", {})
        declarations.append(
            ToolDeclaration(
                name=name.strip(),
                description=str(description),
                parameters=parameters if isinstance(parameters, Mapping) else {},
            )
        )
    return declarations


def backend_messages(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Flatten translated messages to role/content strings for the backend.

    Args:
        messages: Translated chat messages.

    Returns:
        Backend-safe role/content mappings.
    """
    flattened: list[dict[str, str]] = []
    for item in messages:
        content = item.get("content")
        flattened.append(
            {
                "role": str(item.get("role", "user")),
                "content": "" if content is None else str(content),
            }
        )
    return flattened


def _translate_message(item: object, index: int) -> dict[str, Any]:
    """Validate one chat message and reject vision parts.

    Args:
        item: Raw message object.
        index: Zero-based message index for error text.

    Returns:
        A normalized message mapping.

    Raises:
        RequestValidationFailure: If the message is invalid or includes vision.
    """
    if not isinstance(item, Mapping):
        raise RequestValidationFailure(
            f"Message {index} must be an object.",
            remediation="Send messages as objects with role and content.",
        )
    role = item.get("role")
    if role not in {"system", "user", "assistant", "tool"}:
        raise RequestValidationFailure(
            f"Message {index} has an unsupported role.",
            remediation="Use role system, user, assistant, or tool.",
        )
    content = item.get("content")
    if _has_vision_parts(content):
        raise RequestValidationFailure(
            "vision is not available",
            remediation="Send text-only content. Image parts are not supported in this release.",
        )
    if content is not None and not isinstance(content, str):
        raise RequestValidationFailure(
            f"Message {index} content must be a string.",
            remediation="Send text content as a string.",
        )
    if role == "tool" and not item.get("tool_call_id"):
        raise RequestValidationFailure(
            f"Message {index} with role tool must include tool_call_id.",
            remediation="Echo the tool call id from the assistant tool_calls.",
        )
    message: dict[str, Any] = {"role": role, "content": content}
    if "tool_calls" in item:
        message["tool_calls"] = item["tool_calls"]
    if "tool_call_id" in item:
        message["tool_call_id"] = item["tool_call_id"]
    return message


def _has_vision_parts(content: object) -> bool:
    """Return whether content includes image or ``image_url`` parts.

    Args:
        content: Message content value.

    Returns:
        True when vision parts are present.
    """
    if not isinstance(content, list):
        return False
    for part in content:
        if not isinstance(part, Mapping):
            continue
        part_type = str(part.get("type", "")).lower()
        if part_type in {"image_url", "image"} or "image_url" in part or "image" in part:
            return True
    return False


def _optional_float(value: object, *, default: float, name: str) -> float:
    """Coerce an optional numeric field.

    Args:
        value: Raw field value, or ``None``.
        default: Default when the field is omitted.
        name: Field name for errors.

    Returns:
        The numeric value.

    Raises:
        RequestValidationFailure: If the value is present but not numeric.
    """
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise RequestValidationFailure(
            f"{name} must be a number.",
            remediation=f"Pass a numeric {name} or omit the field.",
        )
    return float(value)


def _optional_int(value: object, *, default: int, name: str) -> int:
    """Coerce an optional integer field.

    Args:
        value: Raw field value, or ``None``.
        default: Default when the field is omitted.
        name: Field name for errors.

    Returns:
        The integer value.

    Raises:
        RequestValidationFailure: If the value is present but not an integer.
    """
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise RequestValidationFailure(
            f"{name} must be an integer.",
            remediation=f"Pass an integer {name} or omit the field.",
        )
    return value
