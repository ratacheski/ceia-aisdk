"""Integration tests for optional Bearer auth and localhost CORS."""

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
    def __init__(self) -> None:
        self.llm = _StubLLM()

    @asynccontextmanager
    async def hold(self, alias: str) -> Any:
        del alias
        yield self.llm


def _client(*, token: str | None = None, cors_open: bool = False) -> TestClient:
    return TestClient(create_app(token=token, cors_open=cors_open, pool=_StubPool()))


def test_missing_and_wrong_bearer_are_401() -> None:
    client = _client(token="secret")
    missing = client.get("/v1/models")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "invalid_api_key"
    assert missing.json()["error"]["remediation"]
    wrong = client.get("/v1/models", headers={"Authorization": "Bearer other"})
    assert wrong.status_code == 401
    basic = client.get("/v1/models", headers={"Authorization": "Basic secret"})
    assert basic.status_code == 401
    assert "Traceback" not in missing.text


def test_matching_bearer_allows_models_and_chat() -> None:
    client = _client(token="secret")
    headers = {"Authorization": "Bearer secret"}
    models = client.get("/v1/models", headers=headers)
    assert models.status_code == 200, models.text
    chat = client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"model": "llm/small", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert chat.status_code == 200, chat.text


def test_unset_token_does_not_require_auth() -> None:
    client = _client()
    assert client.get("/v1/models").status_code == 200


def test_default_cors_allows_localhost_and_rejects_foreign() -> None:
    client = _client()
    local = client.get("/v1/models", headers={"Origin": "http://localhost:3000"})
    assert local.status_code == 200
    assert local.headers.get("access-control-allow-origin") == "http://localhost:3000"
    loopback = client.get("/v1/models", headers={"Origin": "http://127.0.0.1:3000"})
    assert loopback.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"
    foreign = client.get("/v1/models", headers={"Origin": "http://example.com"})
    assert foreign.status_code == 200
    assert foreign.headers.get("access-control-allow-origin") != "http://example.com"


def test_cors_flag_allows_any_origin() -> None:
    client = _client(cors_open=True)
    foreign = client.get("/v1/models", headers={"Origin": "http://example.com"})
    assert foreign.status_code == 200
    assert foreign.headers.get("access-control-allow-origin") == "*"
    assert foreign.headers.get("access-control-allow-credentials") in {None, "false"}
