"""Unit tests for ``LLM.complete`` text versus structured tool calls."""

from __future__ import annotations

from pathlib import Path

import pytest

from ceia_aisdk.errors import CapabilityError
from ceia_aisdk.llm import LLM, CompletionResult, ToolCall, ToolDeclaration
from conftest import FakeBackend


def _weather_tool() -> ToolDeclaration:
    return ToolDeclaration(
        name="get_weather",
        description="Return a stub weather string for a city.",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        handler=lambda city: f"sunny in {city}",
    )


def test_complete_returns_text_on_fake_backend(
    fake_llm_catalog: Path, fake_backend: FakeBackend
) -> None:
    del fake_llm_catalog
    model = LLM(device="cpu")
    result = model.complete([{"role": "user", "content": "Say only: ok"}])
    assert isinstance(result, CompletionResult)
    assert result.content == "ok"
    assert result.tool_calls is None
    assert fake_backend.calls[-1]["kind"] == "complete"
    assert isinstance(model.chat("Say only: ok"), str)


def test_complete_returns_tool_calls_without_running_handler(
    fake_llm_catalog: Path, fake_backend: FakeBackend
) -> None:
    del fake_llm_catalog
    handler_ran = {"value": False}

    def _handler(city: str) -> str:
        handler_ran["value"] = True
        return f"sunny in {city}"

    tool = ToolDeclaration(
        name="get_weather",
        description="weather",
        parameters={"type": "object", "properties": {"city": {"type": "string"}}},
        handler=_handler,
    )
    fake_backend.tool_calls = (
        ToolCall(id="call_1", name="get_weather", arguments='{"city":"Lisbon"}'),
    )
    model = LLM("medium", device="cpu")
    result = model.complete(
        [{"role": "user", "content": "Weather in Lisbon?"}],
        tools=[tool],
    )
    assert result.tool_calls
    assert result.tool_calls[0].name == "get_weather"
    assert "Lisbon" in result.tool_calls[0].arguments
    assert handler_ran["value"] is False
    assert isinstance(model.chat("still str"), str)


def test_complete_tools_without_capability_raise(
    fake_llm_catalog: Path, fake_backend: FakeBackend
) -> None:
    del fake_llm_catalog, fake_backend
    model = LLM(device="cpu")
    with pytest.raises(CapabilityError) as exc_info:
        model.complete(
            [{"role": "user", "content": "hi"}],
            tools=[_weather_tool()],
        )
    assert "tool_use" in str(exc_info.value).lower() or "tool" in exc_info.value.remediation.lower()
