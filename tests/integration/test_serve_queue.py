"""Integration tests for HTTP 429 when the admission queue is full."""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import httpx

from ceia_aisdk.server.app import create_app
from ceia_aisdk.server.pool import ModelPool


class _SlowLLM:
    def chat(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> str:
        del prompt, max_tokens, temperature, seed
        time.sleep(0.3)
        return "ok"


def test_ninth_waiter_returns_429_and_queued_work_completes(
    isolated_cache_dir: Path,
) -> None:
    app = create_app(pool=ModelPool(factory=lambda alias: _SlowLLM(), max_waiters=8))
    payload = {"model": "llm/small", "messages": [{"role": "user", "content": "hi"}]}

    async def _run() -> list[int]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            tasks = [
                asyncio.create_task(client.post("/v1/chat/completions", json=payload))
                for _ in range(10)
            ]
            responses = await asyncio.gather(*tasks)
        return [response.status_code for response in responses]

    codes = asyncio.run(_run())
    assert 429 in codes
    assert codes.count(200) == 9
    cache_blob = " ".join(path.name for path in isolated_cache_dir.rglob("*"))
    assert "conversation" not in cache_blob.lower()
    assert "history" not in cache_blob.lower()


def test_429_envelope_is_stable() -> None:
    gate = threading.Event()

    class _BlockedLLM:
        def chat(self, prompt: str, **kwargs: object) -> str:
            del prompt, kwargs
            gate.wait(timeout=2)
            return "ok"

    app = create_app(pool=ModelPool(factory=lambda alias: _BlockedLLM(), max_waiters=8))
    payload = {"model": "llm/small", "messages": [{"role": "user", "content": "hi"}]}

    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            inflight = [asyncio.create_task(client.post("/v1/chat/completions", json=payload))]
            await asyncio.sleep(0.05)
            waiters = [
                asyncio.create_task(client.post("/v1/chat/completions", json=payload))
                for _ in range(8)
            ]
            await asyncio.sleep(0.05)
            overflow = await client.post("/v1/chat/completions", json=payload)
            gate.set()
            await asyncio.gather(*inflight, *waiters)
            return overflow

    overflow = asyncio.run(_run())
    assert overflow.status_code == 429
    body = overflow.json()
    assert body["error"]["type"] == "overloaded_error"
    assert body["error"]["remediation"]
    assert "traceback" not in overflow.text.lower()
