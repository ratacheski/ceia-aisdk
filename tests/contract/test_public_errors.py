"""Contract tests for the public SDK error hierarchy."""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from ceia_aisdk.errors import AISDKError, ConfigError, DeviceError

_ASCII_DOC_RE = re.compile(r"^[\x20-\x7E\n]+$")


def test_public_error_hierarchy() -> None:
    assert issubclass(AISDKError, Exception)
    assert issubclass(ConfigError, AISDKError)
    assert issubclass(DeviceError, AISDKError)
    assert ConfigError is not DeviceError


def test_constructor_requires_keyword_remediation() -> None:
    signature = inspect.signature(AISDKError.__init__)
    parameters = signature.parameters
    assert "message" in parameters
    assert "remediation" in parameters
    assert parameters["remediation"].kind is inspect.Parameter.KEYWORD_ONLY


def test_nonempty_remediation_is_public() -> None:
    error = AISDKError("configuration is invalid", remediation="set device to cpu")
    assert error.remediation == "set device to cpu"
    assert str(error) == "configuration is invalid"
    assert error.args == ("configuration is invalid",)


def test_subclasses_preserve_remediation() -> None:
    config_error = ConfigError("invalid log_level", remediation="use WARNING")
    device_error = DeviceError("cuda is unavailable", remediation="use device=cpu")
    assert isinstance(config_error, AISDKError)
    assert isinstance(device_error, AISDKError)
    assert config_error.remediation == "use WARNING"
    assert device_error.remediation == "use device=cpu"


@pytest.mark.parametrize("cls", [AISDKError, ConfigError, DeviceError])
def test_error_classes_have_english_docstrings(cls: type[AISDKError]) -> None:
    docstring = inspect.getdoc(cls)
    assert docstring
    assert _ASCII_DOC_RE.match(docstring)
    assert len(docstring.split()) >= 3
    init_doc = inspect.getdoc(cls.__init__)
    assert init_doc
    assert "message" in init_doc.lower()
    assert "remediation" in init_doc.lower()


@pytest.mark.parametrize("cls", [AISDKError, ConfigError, DeviceError])
@pytest.mark.parametrize(
    ("message", "remediation"),
    [("", "do this"), ("   ", "do this"), ("failed", ""), ("failed", "   ")],
)
def test_empty_message_or_remediation_is_rejected(
    cls: type[AISDKError], message: str, remediation: str
) -> None:
    with pytest.raises(ValueError):
        cls(message, remediation=remediation)


def test_config_error_chains_without_leaking_file_contents(isolated_home: Path) -> None:
    secret = "s3cret-token-should-never-leak"
    config_dir = isolated_home / ".ceia-aisdk"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(f'[core\npassword = "{secret}"\n', encoding="utf-8")
    from ceia_aisdk import AISDKConfig

    with pytest.raises(ConfigError) as exc_info:
        AISDKConfig.load()
    error = exc_info.value
    assert error.__cause__ is not None
    assert secret not in str(error)
    assert secret not in error.remediation
    assert error.remediation.strip()


def test_device_error_mentions_cpu_remediation() -> None:
    from ceia_aisdk.hardware import get_device

    with pytest.raises(DeviceError) as exc_info:
        get_device("cuda:oops")
    assert "cpu" in exc_info.value.remediation.lower()
    assert exc_info.value.remediation.strip()
