"""Unit tests for session history retention and overflow errors."""

from __future__ import annotations

from pathlib import Path

import pytest

from ceia_aisdk.errors import GenerationError
from ceia_aisdk.llm import LLM, Session
from conftest import FakeBackend


def test_session_retains_two_turns(fake_llm_catalog: Path, fake_backend: FakeBackend) -> None:
    del fake_llm_catalog
    fake_backend.text = "noted"
    session = LLM(device="cpu").session(system="Be brief.")
    assert isinstance(session, Session)
    first = session.send("My name is Ada.")
    fake_backend.text = "Ada"
    second = session.send("What is my name?")
    assert first
    assert second
    generate_calls = [call for call in fake_backend.calls if call["kind"] == "generate"]
    assert len(generate_calls) == 2
    second_messages = generate_calls[1]["messages"]
    roles = [item["role"] for item in second_messages]
    assert roles[:2] == ["system", "user"]
    assert "Ada" in second_messages[1]["content"]
    assert any(item["role"] == "assistant" for item in second_messages)


def test_session_context_overflow_raises_generation_error(
    fake_llm_catalog: Path, fake_backend: FakeBackend
) -> None:
    del fake_llm_catalog
    fake_backend.raise_overflow = True
    session = LLM(device="cpu").session()
    with pytest.raises(GenerationError) as exc_info:
        session.send("This prompt is too long")
    assert exc_info.value.remediation.strip()
    remediation = exc_info.value.remediation.lower()
    assert "history" in remediation or "context" in remediation


def test_chat_does_not_share_session_history(
    fake_llm_catalog: Path, fake_backend: FakeBackend
) -> None:
    del fake_llm_catalog
    model = LLM(device="cpu")
    session = model.session()
    session.send("remember this")
    model.chat("unrelated")
    last = fake_backend.calls[-1]
    assert last["messages"] == [{"role": "user", "content": "unrelated"}]


def test_prompts_are_not_logged_at_warning(
    fake_llm_catalog: Path,
    fake_backend: FakeBackend,
    caplog: pytest.LogCaptureFixture,
) -> None:
    del fake_llm_catalog
    caplog.set_level("WARNING")
    secret = "UNIQUE_PROMPT_TOKEN_DO_NOT_LOG"
    LLM(device="cpu").chat(secret)
    assert secret not in caplog.text
    assert fake_backend.calls
