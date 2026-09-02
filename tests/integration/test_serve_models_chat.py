"""Integration tests for ``GET /v1/models`` and non-stream chat completions."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ceia_aisdk.server.app import create_app


class _StubLLM:
    def __init__(self) -> None:
        self.chat_calls: list[dict[str, Any]] = []

    def chat(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.8,
        seed: int | None = None,
    ) -> str:
        self.chat_calls.append(
            {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "seed": seed,
            }
        )
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


def test_models_list_is_opaque_and_fast(fake_llm_catalog: object) -> None:
    del fake_llm_catalog
    client = TestClient(create_app())
    response = client.get("/v1/models")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["object"] == "list"
    ids = [row["id"] for row in body["data"]]
    assert ids
    assert all(item.startswith("llm/") for item in ids)
    assert "@" not in "".join(ids)
    blob = response.text.lower()
    assert "huggingface" not in blob
    assert ".gguf" not in blob
    assert "tool_use" not in blob
    for row in body["data"]:
        assert row["object"] == "model"
        assert row["owned_by"] == "ceia-aisdk"


def test_create_app_does_not_load_llama_cpp() -> None:
    import sys

    before = "llama_cpp" in sys.modules
    create_app()
    if not before:
        assert "llama_cpp" not in sys.modules


def test_non_stream_chat_returns_nonempty_text() -> None:
    llm = _StubLLM()
    client = TestClient(create_app(pool=_StubPool(llm)))
    response = client.post(
        "/v1/chat/completions",
        json={"model": "llm/small", "messages": [{"role": "user", "content": "Say only: ok"}]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "llm/small"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["choices"][0]["message"]["content"]
    assert body["choices"][0]["finish_reason"] == "stop"
    assert llm.chat_calls
    assert llm.chat_calls[0]["prompt"] == "Say only: ok"


def test_two_requests_do_not_persist_history() -> None:
    llm = _StubLLM()
    client = TestClient(create_app(pool=_StubPool(llm)))
    first = {"model": "llm/small", "messages": [{"role": "user", "content": "one"}]}
    second = {"model": "llm/small", "messages": [{"role": "user", "content": "two"}]}
    assert client.post("/v1/chat/completions", json=first).status_code == 200
    assert client.post("/v1/chat/completions", json=second).status_code == 200
    assert [call["prompt"] for call in llm.chat_calls] == ["one", "two"]


def test_unknown_alias_maps_to_404(monkeypatch: pytest.MonkeyPatch) -> None:
    from ceia_aisdk.errors import ModelNotFoundError

    class _MissingPool:
        @asynccontextmanager
        async def hold(self, alias: str) -> Any:
            raise ModelNotFoundError(
                f"Alias {alias} is not in the active catalog.",
                remediation="Use llm/small.",
            )
            yield None

    client = TestClient(create_app(pool=_MissingPool()))
    response = client.post(
        "/v1/chat/completions",
        json={"model": "llm/missing", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 404, response.text
    body = response.json()
    assert "traceback" not in response.text.lower()
    assert body["error"]["remediation"]
    assert body["error"]["message"]


@pytest.mark.allow_llama_cpp
def test_live_gguf_chat_when_fixture_present(llm_fixture_catalog: object) -> None:
    del llm_fixture_catalog
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "llm/small",
            "messages": [{"role": "user", "content": "Say only: ok"}],
            "max_tokens": 16,
            "temperature": 0.0,
            "seed": 1,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["choices"][0]["message"]["content"].strip()
