"""Integration tests for streaming and sessions."""

from __future__ import annotations

from pathlib import Path

import pytest

from ceia_aisdk.llm import LLM

pytestmark = [pytest.mark.allow_llama_cpp, pytest.mark.requires_llm_fixture]


def test_stream_yields_chunks_and_nonempty_text(llm_fixture_catalog: Path) -> None:
    del llm_fixture_catalog
    model = LLM(device="cpu")
    chunks = list(model.stream("Say only: ok", max_tokens=32, temperature=0, seed=1))
    assert chunks
    assert all(isinstance(chunk, str) for chunk in chunks)
    assert "".join(chunks).strip()


def test_session_send_returns_nonempty_string(llm_fixture_catalog: Path) -> None:
    del llm_fixture_catalog
    session = LLM(device="cpu").session(system="Answer briefly.")
    first = session.send("Say hi.", max_tokens=32, temperature=0, seed=1)
    second = session.send("Say hi again.", max_tokens=32, temperature=0, seed=2)
    assert first.strip()
    assert second.strip()
