"""Integration tests for an official OpenAI client against the ASGI app."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from openai import AsyncOpenAI

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


def test_official_client_completes_chat() -> None:
    app = create_app(pool=_StubPool(_StubLLM()))

    async def _complete() -> str | None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            client = AsyncOpenAI(
                api_key="unused",
                base_url="http://test/v1",
                http_client=http_client,
            )
            completion = await client.chat.completions.create(
                model="llm/small",
                messages=[{"role": "user", "content": "Say only: ok"}],
            )
            return completion.choices[0].message.content

    content = asyncio.run(_complete())
    assert content
    assert "ok" in content.lower()
