"""Integration tests for reserved embeddings/audio/vision refusals."""

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
    @asynccontextmanager
    async def hold(self, alias: str) -> Any:
        del alias
        yield _StubLLM()


def _client() -> TestClient:
    return TestClient(create_app(pool=_StubPool()))


def test_reserved_embeddings_and_audio_are_501() -> None:
    client = _client()
    for path in ("/v1/embeddings", "/v1/audio/transcriptions", "/v1/audio/speech"):
        response = client.post(path, json={})
        assert response.status_code == 501, (path, response.text)
        body = response.json()
        assert body["error"]["remediation"]
        assert "traceback" not in response.text.lower()


def test_vision_parts_are_400() -> None:
    client = _client()
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "llm/small",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "what"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "https://example.invalid/a.png"},
                        },
                    ],
                }
            ],
        },
    )
    assert response.status_code == 400, response.text
    assert "vision" in response.json()["error"]["message"].lower()


def test_unknown_openai_products_are_404() -> None:
    client = _client()
    for path in ("/v1/assistants", "/v1/batches", "/v1/files", "/v1/fine-tuning"):
        response = client.get(path)
        assert response.status_code == 404, (path, response.text)
        assert response.json()["error"]["remediation"]
        assert "traceback" not in response.text.lower()


def test_chat_still_works() -> None:
    client = _client()
    response = client.post(
        "/v1/chat/completions",
        json={"model": "llm/small", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200, response.text
