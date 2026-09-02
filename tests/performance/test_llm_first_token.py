"""Opt-in warm first-token measurement for llm/small on the reference machine."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.allow_llama_cpp,
    pytest.mark.skipif(
        os.environ.get("CEIA_AISDK_PERF_LLM") != "1",
        reason="opt-in reference-machine test; set CEIA_AISDK_PERF_LLM=1",
    ),
]


def test_warm_first_token_within_ten_seconds(llm_fixture_catalog: Path) -> None:
    del llm_fixture_catalog
    from ceia_aisdk.llm import LLM

    model = LLM(device="cpu")
    model.chat("Say only: ok", max_tokens=8, temperature=0, seed=1)
    start = time.perf_counter()
    text = model.chat("Say only: ok", max_tokens=8, temperature=0, seed=1)
    elapsed = time.perf_counter() - start
    assert text.strip()
    assert elapsed <= 10.0
