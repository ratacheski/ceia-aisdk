"""Unit tests for layered AISDKConfig resolution and validation."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ceia_aisdk import AISDKConfig
from ceia_aisdk.errors import ConfigError

SECRET = "s3cret-token-should-never-leak"


def _write_toml(home: Path, body: str) -> Path:
    config_dir = home / ".ceia-aisdk"
    config_dir.mkdir()
    path = config_dir / "config.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_defaults_under_isolated_home(isolated_home: Path) -> None:
    config = AISDKConfig.load()
    assert config.device == "auto"
    assert config.cache_dir == isolated_home / ".ceia-aisdk"
    assert config.log_level == "WARNING"
    assert config.offline is False
    assert not (isolated_home / ".ceia-aisdk").exists()


def test_missing_toml_is_not_an_error(isolated_home: Path) -> None:
    del isolated_home
    config = AISDKConfig.load()
    assert config.device == "auto"


def test_empty_toml_is_valid(isolated_home: Path) -> None:
    _write_toml(isolated_home, "")
    config = AISDKConfig.load()
    assert config.device == "auto"
    assert config.offline is False


def test_toml_overrides_defaults(isolated_home: Path) -> None:
    _write_toml(
        isolated_home,
        "\n".join(
            [
                "[core]",
                'device = "cpu"',
                'cache_dir = "~/from-toml"',
                'log_level = "INFO"',
                "offline = true",
                f'password = "{SECRET}"',
            ]
        ),
    )
    config = AISDKConfig.load()
    assert config.device == "cpu"
    assert config.cache_dir == isolated_home / "from-toml"
    assert config.log_level == "INFO"
    assert config.offline is True


def test_environment_overrides_toml(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_toml(
        isolated_home,
        "[core]\n"
        'device = "cuda"\n'
        'cache_dir = "~/from-toml"\n'
        'log_level = "DEBUG"\n'
        "offline = false\n",
    )
    monkeypatch.setenv("CEIA_AISDK_DEVICE", "cpu")
    monkeypatch.setenv("CEIA_AISDK_CACHE_DIR", "/tmp/ceia-from-env")
    monkeypatch.setenv("CEIA_AISDK_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("CEIA_AISDK_OFFLINE", "1")
    config = AISDKConfig.load()
    assert config.device == "cpu"
    assert config.cache_dir == Path("/tmp/ceia-from-env")
    assert config.log_level == "ERROR"
    assert config.offline is True


def test_explicit_overrides_environment_and_toml(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_toml(isolated_home, '[core]\ndevice = "cuda"\nlog_level = "DEBUG"\noffline = true\n')
    monkeypatch.setenv("CEIA_AISDK_DEVICE", "cuda:0")
    monkeypatch.setenv("CEIA_AISDK_LOG_LEVEL", "INFO")
    monkeypatch.setenv("CEIA_AISDK_OFFLINE", "1")
    config = AISDKConfig.load(device="cpu", log_level="WARNING", offline=False)
    assert config.device == "cpu"
    assert config.log_level == "WARNING"
    assert config.offline is False


def test_mixed_sources_resolve_independently(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_toml(isolated_home, '[core]\ncache_dir = "~/from-toml"\nlog_level = "DEBUG"\n')
    monkeypatch.setenv("CEIA_AISDK_OFFLINE", "1")
    config = AISDKConfig.load(device="cpu")
    assert config.device == "cpu"
    assert config.cache_dir == isolated_home / "from-toml"
    assert config.log_level == "DEBUG"
    assert config.offline is True


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("auto", "auto"),
        ("cpu", "cpu"),
        ("cuda", "cuda"),
        ("cuda:0", "cuda:0"),
        ("cuda:12", "cuda:12"),
    ],
)
def test_valid_devices(isolated_home: Path, value: str, expected: str) -> None:
    del isolated_home
    assert AISDKConfig.load(device=value).device == expected


@pytest.mark.parametrize(
    "value", ["CPU", "cuda:01", "cuda:-1", "cuda:0.0", "gpu", "cuda:", " cuda"]
)
def test_invalid_device_is_rejected(isolated_home: Path, value: str) -> None:
    del isolated_home
    with pytest.raises(ConfigError) as exc_info:
        AISDKConfig.load(device=value)
    assert exc_info.value.remediation
    assert "device" in str(exc_info.value).lower()
    assert SECRET not in str(exc_info.value)


def test_invalid_lower_priority_is_shadowed(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_toml(isolated_home, '[core]\ndevice = "nope"\nlog_level = "verbose"\noffline = "yes"\n')
    monkeypatch.setenv("CEIA_AISDK_DEVICE", "not-a-device")
    config = AISDKConfig.load(device="cpu", log_level="INFO", offline=False)
    assert config.device == "cpu"
    assert config.log_level == "INFO"
    assert config.offline is False


def test_empty_environment_value_does_not_fall_through(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_toml(isolated_home, '[core]\ndevice = "cpu"\n')
    monkeypatch.setenv("CEIA_AISDK_DEVICE", "")
    with pytest.raises(ConfigError) as exc_info:
        AISDKConfig.load()
    assert "device" in str(exc_info.value).lower()
    assert "environment" in str(exc_info.value).lower()


@pytest.mark.parametrize("value", ["info", "WARN", " warning", "WARNING\n"])
def test_log_level_is_strict(isolated_home: Path, value: str) -> None:
    del isolated_home
    with pytest.raises(ConfigError) as exc_info:
        AISDKConfig.load(log_level=value)
    assert "log_level" in str(exc_info.value)


def test_offline_environment_accepts_only_zero_or_one(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    del isolated_home
    monkeypatch.setenv("CEIA_AISDK_OFFLINE", "true")
    with pytest.raises(ConfigError) as exc_info:
        AISDKConfig.load()
    assert "offline" in str(exc_info.value).lower()
    assert "0" in str(exc_info.value) and "1" in str(exc_info.value)


def test_offline_toml_requires_boolean(isolated_home: Path) -> None:
    _write_toml(isolated_home, '[core]\noffline = "1"\n')
    with pytest.raises(ConfigError) as exc_info:
        AISDKConfig.load()
    assert "offline" in str(exc_info.value).lower()
    assert SECRET not in str(exc_info.value)
    assert '"1"' not in str(exc_info.value) or "toml" in str(exc_info.value).lower()


def test_malformed_toml_is_privacy_safe(isolated_home: Path) -> None:
    _write_toml(isolated_home, f'[core\ndevice = "cpu"\npassword = "{SECRET}"\n')
    with pytest.raises(ConfigError) as exc_info:
        AISDKConfig.load()
    message = str(exc_info.value)
    assert exc_info.value.remediation
    assert SECRET not in message
    assert "[core" not in message
    assert "device = " not in message


def test_unreadable_toml_raises_config_error(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_toml(isolated_home, '[core]\ndevice = "cpu"\n')
    original = Path.read_text

    def boom(self: Path, *args: object, **kwargs: object) -> str:
        if self == path:
            raise PermissionError("Permission denied")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", boom)
    with pytest.raises(ConfigError) as exc_info:
        AISDKConfig.load()
    assert "unreadable" in str(exc_info.value).lower() or "read" in str(exc_info.value).lower()
    assert exc_info.value.remediation


def test_unknown_toml_keys_are_ignored(isolated_home: Path) -> None:
    _write_toml(isolated_home, '[other]\nfoo = 1\n[core]\ndevice = "cpu"\nfuture = true\n')
    config = AISDKConfig.load()
    assert config.device == "cpu"


def test_load_does_not_configure_root_logger(isolated_home: Path) -> None:
    del isolated_home
    root = logging.getLogger()
    before = (root.level, list(root.handlers))
    AISDKConfig.load()
    assert (root.level, list(root.handlers)) == before
