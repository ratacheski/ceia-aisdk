"""Integration tests for real-backend LLM chat against the tiny GGUF fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

from ceia_aisdk.llm import LLM

pytestmark = [pytest.mark.allow_llama_cpp, pytest.mark.requires_llm_fixture]


def test_real_backend_chat_returns_nonempty_string(llm_fixture_catalog: Path) -> None:
    del llm_fixture_catalog
    model = LLM(device="cpu")
    text = model.chat("Say only: ok", max_tokens=32, temperature=0, seed=1)
    assert isinstance(text, str)
    assert text.strip()
