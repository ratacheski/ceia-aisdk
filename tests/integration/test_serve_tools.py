"""Integration tests for OpenAI tools on ``/v1/chat/completions``."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any

from fastapi.testclient import TestClient

from ceia_aisdk.errors import CapabilityError
from ceia_aisdk.llm.tools import CompletionResult, ToolCall
from ceia_aisdk.server.app import create_app


class _ToolLLM:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        messages: Sequence[Mapping[str, object]],
        *,
        tools: object = None,
        tool_choice: object = None,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> CompletionResult:
        self.calls.append(
            {
                "messages": list(messages),
                "tools": tools,
                "tool_choice": tool_choice,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "seed": seed,
            }
        )
        if tools:
            return CompletionResult(
                tool_calls=(
                    ToolCall(
                        id="call_weather",
                        name="get_weather",
                        arguments='{"city":"Lisbon"}',
                    ),
                )
            )
        last = messages[-1] if messages else {}
        if last.get("role") == "tool":
            return CompletionResult(content="16C in Lisbon")
        return CompletionResult(content="ok")


class _NoToolLLM:
    def complete(
        self, messages: Sequence[Mapping[str, object]], **kwargs: object
    ) -> CompletionResult:
        del messages
        if kwargs.get("tools"):
            raise CapabilityError(
                "The selected alias does not support tool use.",
                remediation="Choose an alias whose public capabilities include tool_use.",
            )
        return CompletionResult(content="ok")


class _StubPool:
    def __init__(self, llm: object) -> None:
        self.llm = llm

    @asynccontextmanager
    async def hold(self, alias: str) -> Any:
        del alias
        yield self.llm


_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }
]


def test_tools_return_tool_calls_and_accept_tool_follow_up() -> None:
    llm = _ToolLLM()
    client = TestClient(create_app(pool=_StubPool(llm)))
    first = client.post(
        "/v1/chat/completions",
        json={
            "model": "llm/medium",
            "messages": [{"role": "user", "content": "Weather in Lisbon?"}],
            "tools": _TOOLS,
        },
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["choices"][0]["finish_reason"] == "tool_calls"
    tool_calls = body["choices"][0]["message"]["tool_calls"]
    assert tool_calls[0]["function"]["name"] == "get_weather"
    assert "Lisbon" in tool_calls[0]["function"]["arguments"]
    follow = client.post(
        "/v1/chat/completions",
        json={
            "model": "llm/medium",
            "messages": [
                {"role": "user", "content": "Weather in Lisbon?"},
                body["choices"][0]["message"],
                {
                    "role": "tool",
                    "tool_call_id": tool_calls[0]["id"],
                    "content": "16C",
                },
            ],
        },
    )
    assert follow.status_code == 200, follow.text
    assert follow.json()["choices"][0]["message"]["content"] == "16C in Lisbon"
    assert llm.calls[-1]["messages"][-1]["role"] == "tool"


def test_stream_emits_delta_tool_calls() -> None:
    client = TestClient(create_app(pool=_StubPool(_ToolLLM())))
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "llm/medium",
            "messages": [{"role": "user", "content": "Weather?"}],
            "tools": _TOOLS,
            "stream": True,
        },
    )
    assert response.status_code == 200, response.text
    assert "delta" in response.text
    assert "tool_calls" in response.text
    assert "data: [DONE]" in response.text


def test_tools_without_capability_are_400() -> None:
    client = TestClient(create_app(pool=_StubPool(_NoToolLLM())))
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "llm/small",
            "messages": [{"role": "user", "content": "Weather?"}],
            "tools": _TOOLS,
        },
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["remediation"]
    assert "traceback" not in response.text.lower()
