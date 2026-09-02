"""Integration tests that forced CPU generation works."""

from __future__ import annotations

from pathlib import Path

import pytest

from ceia_aisdk.llm import LLM
from conftest import FakeBackend

pytestmark = pytest.mark.requires_llm_fixture


def test_forced_cpu_chat_with_fake_backend(
    fake_llm_catalog: Path, fake_backend: FakeBackend
) -> None:
    del fake_llm_catalog
    model = LLM(device="cpu")
    assert model.device == "cpu"
    assert fake_backend.n_gpu_layers == 0
    assert model.chat("Say only: ok")


@pytest.mark.allow_llama_cpp
def test_forced_cpu_chat_with_real_backend(llm_fixture_catalog: Path) -> None:
    del llm_fixture_catalog
    model = LLM(device="cpu")
    assert model.device == "cpu"
    assert model.chat("Say only: ok", max_tokens=16, temperature=0, seed=1).strip()
