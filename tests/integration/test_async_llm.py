"""Integration smoke tests for AsyncLLM."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ceia_aisdk.llm import AsyncLLM
from conftest import FakeBackend


def test_async_chat_with_fake_backend(fake_llm_catalog: Path, fake_backend: FakeBackend) -> None:
    del fake_llm_catalog

    async def _run() -> str:
        model = AsyncLLM(device="cpu")
        return await asyncio.wait_for(model.chat("Say only: ok"), timeout=10)

    text = asyncio.run(_run())
    assert text
    assert fake_backend.calls


@pytest.mark.allow_llama_cpp
@pytest.mark.requires_llm_fixture
def test_async_chat_with_real_backend(llm_fixture_catalog: Path) -> None:
    del llm_fixture_catalog

    async def _run() -> str:
        model = AsyncLLM(device="cpu")
        return await asyncio.wait_for(
            model.chat("Say only: ok", max_tokens=16, temperature=0, seed=1),
            timeout=30,
        )

    text = asyncio.run(_run())
    assert text.strip()
