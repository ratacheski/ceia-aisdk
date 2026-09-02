"""Unit tests for OpenAI chat-request translation."""

from __future__ import annotations

import pytest

from ceia_aisdk.server.messages import RequestValidationFailure, parse_chat_request


def test_requires_model_and_messages() -> None:
    with pytest.raises(RequestValidationFailure) as missing_model:
        parse_chat_request({"messages": [{"role": "user", "content": "hi"}]})
    assert missing_model.value.status_code == 400
    with pytest.raises(RequestValidationFailure) as missing_messages:
        parse_chat_request({"model": "llm/small"})
    assert missing_messages.value.status_code == 400
    with pytest.raises(RequestValidationFailure):
        parse_chat_request({"model": "llm/small", "messages": []})


def test_defaults_temperature_and_max_tokens() -> None:
    parsed = parse_chat_request(
        {"model": "llm/small", "messages": [{"role": "user", "content": "hi"}]}
    )
    assert parsed.model == "llm/small"
    assert parsed.temperature == 0.8
    assert parsed.max_tokens == 512
    assert parsed.stream is False
    assert parsed.seed is None
    assert parsed.messages == [{"role": "user", "content": "hi"}]


def test_rejects_n_not_equal_to_one() -> None:
    with pytest.raises(RequestValidationFailure) as exc_info:
        parse_chat_request(
            {
                "model": "llm/small",
                "messages": [{"role": "user", "content": "hi"}],
                "n": 2,
            }
        )
    assert exc_info.value.status_code == 400
    assert "n" in str(exc_info.value).lower()


def test_rejects_vision_image_parts() -> None:
    with pytest.raises(RequestValidationFailure) as exc_info:
        parse_chat_request(
            {
                "model": "llm/small",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "what is this"},
                            {
                                "type": "image_url",
                                "image_url": {"url": "https://example.invalid/a.png"},
                            },
                        ],
                    }
                ],
            }
        )
    assert exc_info.value.status_code == 400
    assert "vision" in str(exc_info.value).lower()


def test_accepts_explicit_sampling_and_seed() -> None:
    parsed = parse_chat_request(
        {
            "model": "llm/medium",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.0,
            "max_tokens": 16,
            "seed": 7,
            "stream": True,
        }
    )
    assert parsed.temperature == 0.0
    assert parsed.max_tokens == 16
    assert parsed.seed == 7
    assert parsed.stream is True
