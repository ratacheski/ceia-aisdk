"""Integration tests for SSE chat completions."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi.testclient import TestClient

from ceia_aisdk.server.app import create_app


class _StubLLM:
    def chat(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> str:
        del prompt, max_tokens, temperature, seed
        return "ok"

    def stream(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> Iterator[str]:
        del prompt, max_tokens, temperature, seed
        yield "ok"


class _StubPool:
    def __init__(self, llm: _StubLLM) -> None:
        self.llm = llm

    @asynccontextmanager
    async def hold(self, alias: str) -> Any:
        del alias
        yield self.llm


def test_stream_emits_data_chunk_and_done() -> None:
    client = TestClient(create_app(pool=_StubPool(_StubLLM())))
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "llm/small",
            "messages": [{"role": "user", "content": "Say only: ok"}],
            "stream": True,
        },
    )
    assert response.status_code == 200, response.text
    assert "text/event-stream" in response.headers.get("content-type", "")
    text = response.text
    assert "data:" in text
    assert "data: [DONE]" in text
    assert "chat.completion.chunk" in text
    assert "ok" in text
