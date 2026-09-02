"""Unit tests for the tool-use capability gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from ceia_aisdk.errors import CapabilityError
from ceia_aisdk.llm import LLM, ToolDeclaration
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


def test_tools_on_alias_without_tool_use_raise(
    fake_llm_catalog: Path, fake_backend: FakeBackend
) -> None:
    del fake_llm_catalog, fake_backend
    with pytest.raises(CapabilityError) as exc_info:
        LLM(device="cpu", tools=[_weather_tool()])
    assert "tool_use" in str(exc_info.value).lower() or "tool" in exc_info.value.remediation.lower()
    assert exc_info.value.remediation.strip()


def test_tools_accepted_when_capability_is_present(
    fake_llm_catalog: Path, fake_backend: FakeBackend
) -> None:
    del fake_llm_catalog
    model = LLM("medium", device="cpu", tools=[_weather_tool()])
    assert model.alias.startswith("llm/medium@")
    assert model.chat("hello")
    assert fake_backend.calls


def test_get_weather_loop_is_explicitly_skipped_on_tiny_fixture() -> None:
    pytest.skip(
        "tiny CI GGUF cannot demonstrate a get_weather tool loop; "
        "run this scenario on cataloged llm/small on the reference machine"
    )
