"""P0 OpenAI-compatible routes for models and chat completions.

``GET /v1/models`` lists opaque ``llm/<size>`` aliases. ``POST /v1/chat/completions``
maps OpenAI chat and tools onto the library ``complete`` path.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from ceia_aisdk.llm.tools import CompletionResult, ToolCall
from ceia_aisdk.server.messages import (
    ChatRequest,
    backend_messages,
    is_single_user_text,
    parse_chat_request,
    tool_declarations_from_openai,
)
from ceia_aisdk.server.pool import PoolOverflowError


def register_openai_routes(app: FastAPI) -> None:
    """Attach ``/v1/models`` and ``/v1/chat/completions`` to ``app``.

    Args:
        app: FastAPI application created by ``create_app``.
    """

    @app.get("/v1/models")
    def list_models() -> dict[str, Any]:
        """Return opaque LLM size aliases from the active catalog.

        Returns:
            An OpenAI ``list`` object whose ids are ``llm/<size>`` aliases.
        """
        return {
            "object": "list",
            "data": [
                {
                    "id": alias,
                    "object": "model",
                    "created": 0,
                    "owned_by": "ceia-aisdk",
                }
                for alias in _llm_size_aliases()
            ],
        }

    @app.post("/v1/chat/completions", response_model=None)
    async def chat_completions(request: Request) -> Response:
        """Complete a stateless chat turn.

        Args:
            request: Incoming ASGI request whose JSON body is an OpenAI chat
                completion payload.

        Returns:
            A chat.completion JSON body or an SSE stream.

        Raises:
            RequestValidationFailure: If the body is invalid.
            PoolOverflowError: If the waiter queue is full.
        """
        payload = await request.json()
        parsed = parse_chat_request(payload)
        pool = request.app.state.pool
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        try:
            async with pool.hold(parsed.model) as llm:
                if parsed.stream:
                    result = await _complete_result(llm, parsed)
                    return StreamingResponse(
                        _sse_events(completion_id, parsed.model, created, result),
                        media_type="text/event-stream",
                    )
                result = await _complete_result(llm, parsed)
        except PoolOverflowError:
            from ceia_aisdk.server.app import error_envelope

            return error_envelope(
                message="The server is overloaded.",
                error_type="overloaded_error",
                remediation="Retry later or send fewer parallel chat requests.",
                status_code=429,
            )
        return JSONResponse(_completion_body(completion_id, parsed.model, created, result))


def _llm_size_aliases() -> list[str]:
    """List unversioned ``llm/<size>`` aliases from the active catalog.

    Returns:
        Opaque aliases with no Hugging Face names or capability claims.
    """
    from ceia_aisdk.registry.catalog import load_catalog

    catalog = load_catalog()
    sizes = catalog.models.get("llm", {})
    return [f"llm/{size}" for size in sizes]


async def _complete_result(llm: Any, parsed: ChatRequest) -> CompletionResult:
    """Generate one completion under the alias lock.

    Args:
        llm: Pooled ``LLM`` or test double.
        parsed: Validated request.

    Returns:
        Text or structured tool calls.
    """
    import asyncio

    declarations = tool_declarations_from_openai(parsed.tools)
    if hasattr(llm, "complete"):
        return await asyncio.to_thread(
            llm.complete,
            parsed.messages,
            tools=declarations or None,
            tool_choice=parsed.tool_choice,
            max_tokens=parsed.max_tokens,
            temperature=parsed.temperature,
            seed=parsed.seed,
        )
    if is_single_user_text(parsed.messages) and hasattr(llm, "chat"):
        text = await asyncio.to_thread(
            llm.chat,
            str(parsed.messages[0]["content"]),
            max_tokens=parsed.max_tokens,
            temperature=parsed.temperature,
            seed=parsed.seed,
        )
        return CompletionResult(content=text)
    if parsed.stream and hasattr(llm, "stream") and is_single_user_text(parsed.messages):
        chunks = await asyncio.to_thread(
            _collect_stream,
            llm.stream(
                str(parsed.messages[0]["content"]),
                max_tokens=parsed.max_tokens,
                temperature=parsed.temperature,
                seed=parsed.seed,
            ),
        )
        return CompletionResult(content="".join(chunks))
    text = await asyncio.to_thread(_backend_generate, llm, parsed, stream=False)
    assert isinstance(text, str)
    return CompletionResult(content=text)


def _collect_stream(chunks: Iterator[str]) -> list[str]:
    """Materialize a text iterator.

    Args:
        chunks: Streaming iterator.

    Returns:
        Collected chunk strings.
    """
    return [chunk for chunk in chunks if chunk]


def _backend_generate(llm: Any, parsed: ChatRequest, *, stream: bool) -> str | list[str]:
    """Call the private backend for multi-turn messages.

    Args:
        llm: Pooled ``LLM`` instance.
        parsed: Validated request.
        stream: Whether to collect stream chunks.

    Returns:
        Assistant text or a list of chunks.
    """
    backend = llm._backend
    messages = backend_messages(parsed.messages)
    if stream:
        return list(
            backend.stream(
                messages,
                max_tokens=parsed.max_tokens,
                temperature=parsed.temperature,
                seed=parsed.seed,
            )
        )
    return backend.generate(
        messages,
        max_tokens=parsed.max_tokens,
        temperature=parsed.temperature,
        seed=parsed.seed,
    )


def _completion_body(
    completion_id: str, model: str, created: int, result: CompletionResult
) -> dict[str, Any]:
    """Build a non-stream OpenAI chat.completion body.

    Args:
        completion_id: ``chatcmpl-`` identifier.
        model: Opaque alias echoed to the client.
        created: Unix timestamp.
        result: Library completion result.

    Returns:
        The JSON-serializable response body.
    """
    if result.tool_calls:
        message = {
            "role": "assistant",
            "content": result.content,
            "tool_calls": [_openai_tool_call(call) for call in result.tool_calls],
        }
        finish_reason = "tool_calls"
    else:
        message = {"role": "assistant", "content": result.content or ""}
        finish_reason = "stop"
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _openai_tool_call(call: ToolCall) -> dict[str, Any]:
    """Serialize one library tool call to the OpenAI wire form.

    Args:
        call: Library tool call.

    Returns:
        An OpenAI ``tool_calls`` item.
    """
    return {
        "id": call.id,
        "type": "function",
        "function": {"name": call.name, "arguments": call.arguments},
    }


def _sse_events(
    completion_id: str,
    model: str,
    created: int,
    result: CompletionResult,
) -> Iterator[str]:
    """Yield SSE ``data:`` lines for text or tool-call completions.

    Args:
        completion_id: ``chatcmpl-`` identifier.
        model: Opaque alias echoed to the client.
        created: Unix timestamp.
        result: Library completion result.

    Yields:
        SSE lines including a terminal ``data: [DONE]``.
    """
    if result.tool_calls:
        deltas = [
            {
                "tool_calls": [
                    {
                        "index": index,
                        **_openai_tool_call(call),
                    }
                ]
            }
            for index, call in enumerate(result.tool_calls)
        ]
        finish_reason = "tool_calls"
    else:
        text = result.content or ""
        deltas = [{"content": text, "role": "assistant"}]
        finish_reason = "stop"
    for index, delta in enumerate(deltas):
        if index == 0 and "role" not in delta:
            delta = {"role": "assistant", **delta}
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
        }
        yield f"data: {json.dumps(payload)}\n\n"
    final = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
    }
    yield f"data: {json.dumps(final)}\n\n"
    yield "data: [DONE]\n\n"
