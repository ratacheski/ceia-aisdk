"""Unit tests for LLMSettings defaults, TOML, environment, and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from ceia_aisdk.errors import ConfigError
from ceia_aisdk.llm.settings import LLMSettings

SECRET = "s3cret-token-should-never-leak"


def _write_toml(home: Path, body: str) -> Path:
    config_dir = home / ".ceia-aisdk"
    config_dir.mkdir()
    path = config_dir / "config.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_defaults_under_isolated_home(isolated_home: Path) -> None:
    settings = LLMSettings.load()
    assert settings.default_alias == "llm/small@latest"
    assert settings.context_length == 8192
    assert not (isolated_home / ".ceia-aisdk").exists()


def test_missing_llm_table_uses_defaults(isolated_home: Path) -> None:
    _write_toml(isolated_home, '[core]\ndevice = "cpu"\n')
    settings = LLMSettings.load()
    assert settings.default_alias == "llm/small@latest"
    assert settings.context_length == 8192


def test_toml_llm_table_overrides_defaults(isolated_home: Path) -> None:
    _write_toml(
        isolated_home,
        "\n".join(
            [
                "[core]",
                'device = "cpu"',
                "[llm]",
                'default_alias = "medium"',
                "context_length = 4096",
                f'password = "{SECRET}"',
            ]
        ),
    )
    settings = LLMSettings.load()
    assert settings.default_alias == "medium"
    assert settings.context_length == 4096


def test_unknown_llm_keys_are_ignored(isolated_home: Path) -> None:
    _write_toml(isolated_home, "[llm]\nfuture_key = 1\ncontext_length = 2048\n")
    settings = LLMSettings.load()
    assert settings.context_length == 2048
    assert settings.default_alias == "llm/small@latest"


def test_environment_overrides_toml(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_toml(
        isolated_home,
        '[llm]\ndefault_alias = "medium"\ncontext_length = 2048\n',
    )
    monkeypatch.setenv("CEIA_AISDK_LLM_DEFAULT_ALIAS", "llm/small@1")
    monkeypatch.setenv("CEIA_AISDK_LLM_CONTEXT_LENGTH", "1024")
    settings = LLMSettings.load()
    assert settings.default_alias == "llm/small@1"
    assert settings.context_length == 1024


def test_explicit_overrides_environment_and_toml(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_toml(isolated_home, '[llm]\ndefault_alias = "medium"\ncontext_length = 2048\n')
    monkeypatch.setenv("CEIA_AISDK_LLM_DEFAULT_ALIAS", "llm/large")
    monkeypatch.setenv("CEIA_AISDK_LLM_CONTEXT_LENGTH", "1024")
    settings = LLMSettings.load(default_alias="llm/small", context_length=512)
    assert settings.default_alias == "llm/small"
    assert settings.context_length == 512


def test_mixed_sources_resolve_independently(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_toml(isolated_home, '[llm]\ndefault_alias = "medium"\n')
    monkeypatch.setenv("CEIA_AISDK_LLM_CONTEXT_LENGTH", "+4096")
    settings = LLMSettings.load()
    assert settings.default_alias == "medium"
    assert settings.context_length == 4096


def test_empty_environment_alias_is_invalid(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    del isolated_home
    monkeypatch.setenv("CEIA_AISDK_LLM_DEFAULT_ALIAS", "")
    with pytest.raises(ConfigError) as exc_info:
        LLMSettings.load()
    assert exc_info.value.remediation.strip()
    assert SECRET not in str(exc_info.value)


def test_invalid_context_length_raises_config_error(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    del isolated_home
    monkeypatch.setenv("CEIA_AISDK_LLM_CONTEXT_LENGTH", "0")
    with pytest.raises(ConfigError) as exc_info:
        LLMSettings.load()
    message = str(exc_info.value).lower()
    assert "context_length" in message or "context" in message
    assert exc_info.value.remediation.strip()


def test_invalid_toml_context_length_does_not_dump_file(isolated_home: Path) -> None:
    _write_toml(
        isolated_home,
        f'[llm]\ncontext_length = -1\npassword = "{SECRET}"\n',
    )
    with pytest.raises(ConfigError) as exc_info:
        LLMSettings.load()
    error = exc_info.value
    assert SECRET not in str(error)
    assert SECRET not in error.remediation
    assert error.remediation.strip()


def test_settings_are_frozen_and_slotted(isolated_home: Path) -> None:
    del isolated_home
    settings = LLMSettings.load()
    with pytest.raises((AttributeError, Exception)):
        settings.default_alias = "medium"  # type: ignore[misc]
    assert getattr(LLMSettings, "__slots__", None) is not None
