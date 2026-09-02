"""Unit tests for LLM construction, defaults, and TTY progress."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from ceia_aisdk import AISDKConfig
from ceia_aisdk.llm import LLM
from conftest import FakeBackend


def test_default_alias_is_small(
    fake_llm_catalog: Path, fake_backend: FakeBackend, isolated_home: Path
) -> None:
    del isolated_home
    model = LLM(device="cpu")
    assert model.alias == "llm/small@1"
    assert model.device == "cpu"
    text = model.chat("Say only: ok")
    assert isinstance(text, str)
    assert text
    assert fake_backend.calls
    assert fake_backend.n_gpu_layers == 0
    assert fake_llm_catalog.is_dir()


def test_unqualified_medium_uses_llm_domain(
    fake_llm_catalog: Path, fake_backend: FakeBackend
) -> None:
    del fake_llm_catalog
    model = LLM("medium", device="cpu")
    assert model.alias.startswith("llm/medium@")
    assert fake_backend.path is not None


def test_explicit_device_overrides_config(
    fake_llm_catalog: Path,
    fake_backend: FakeBackend,
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del fake_llm_catalog
    config_dir = isolated_home / ".ceia-aisdk"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text('[core]\ndevice = "auto"\n', encoding="utf-8")
    monkeypatch.delenv("CEIA_AISDK_DEVICE", raising=False)
    model = LLM(device="cpu", config=AISDKConfig.load())
    assert model.device == "cpu"
    assert fake_backend.n_gpu_layers == 0


def test_tty_progress_is_passed_to_ensure_local(
    fake_llm_catalog: Path,
    fake_backend: FakeBackend,
    monkeypatch: pytest.MonkeyPatch,
    isolated_cache_dir: Path,
) -> None:
    del fake_llm_catalog, fake_backend
    captured: list[Callable[[int, int | None], None] | None] = []
    real_ensure = __import__("ceia_aisdk.registry", fromlist=["ensure_local"]).ensure_local

    def _wrapped(
        alias: str,
        *,
        config: AISDKConfig | None = None,
        domain: str | None = None,
        progress: Callable[[int, int | None], None] | None = None,
    ) -> Path:
        captured.append(progress)
        return real_ensure(alias, config=config, domain=domain, progress=progress)

    monkeypatch.setattr("ceia_aisdk.llm.model.ensure_local", _wrapped)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    LLM(device="cpu")
    assert captured
    assert captured[0] is not None
    assert isolated_cache_dir.is_dir()


def test_non_tty_omits_progress_callback(
    fake_llm_catalog: Path,
    fake_backend: FakeBackend,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del fake_llm_catalog, fake_backend
    captured: list[Callable[[int, int | None], None] | None] = []
    real_ensure = __import__("ceia_aisdk.registry", fromlist=["ensure_local"]).ensure_local

    def _wrapped(
        alias: str,
        *,
        config: AISDKConfig | None = None,
        domain: str | None = None,
        progress: Callable[[int, int | None], None] | None = None,
    ) -> Path:
        captured.append(progress)
        return real_ensure(alias, config=config, domain=domain, progress=progress)

    monkeypatch.setattr("ceia_aisdk.llm.model.ensure_local", _wrapped)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)
    LLM(device="cpu")
    assert captured
    assert captured[0] is None


def test_chat_does_not_retain_history(fake_llm_catalog: Path, fake_backend: FakeBackend) -> None:
    del fake_llm_catalog
    model = LLM(device="cpu")
    model.chat("first")
    model.chat("second")
    assert len(fake_backend.calls) == 2
    assert fake_backend.calls[1]["messages"] == [{"role": "user", "content": "second"}]
