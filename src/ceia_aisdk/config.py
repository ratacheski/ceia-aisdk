"""Immutable layered configuration for the CEIA AI SDK."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ceia_aisdk._logging import get_logger
from ceia_aisdk.errors import ConfigError

_LOGGER = get_logger(__name__)
_CONFIG_DIRNAME = ".ceia-aisdk"
_CONFIG_FILENAME = "config.toml"
_DEFAULT_DEVICE = "auto"
_DEFAULT_CACHE_DIR = "~/.ceia-aisdk"
_DEFAULT_LOG_LEVEL = "WARNING"
_DEFAULT_OFFLINE = False
_LOG_LEVELS: Final[frozenset[str]] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
_DEVICE_RE = re.compile(r"^(?:auto|cpu|cuda|cuda:(?:0|[1-9][0-9]*))$")
_SOURCE_EXPLICIT = "explicit argument"
_SOURCE_ENVIRONMENT = "environment"
_SOURCE_TOML = "configuration file"
_SOURCE_DEFAULT = "default"


@dataclass(frozen=True, slots=True)
class AISDKConfig:
    """Effective, validated SDK configuration snapshot.

    Attributes:
        device: Selected compute device (``auto``, ``cpu``, ``cuda``, or
            ``cuda:N``).
        cache_dir: Expanded cache directory path. The directory is not created.
        log_level: Package log level name.
        offline: Recorded offline intent; this feature does not block downloads.
    """

    device: str
    cache_dir: Path
    log_level: str
    offline: bool

    @classmethod
    def load(
        cls,
        *,
        device: str | None = None,
        cache_dir: str | os.PathLike[str] | None = None,
        log_level: str | None = None,
        offline: bool | None = None,
    ) -> AISDKConfig:
        """Load configuration from explicit arguments, environment, TOML, and defaults.

        Each field is resolved independently. A missing or empty configuration
        file is valid. Loading does not create directories, probe hardware, or
        change the root logger.

        Args:
            device: Explicit device override, or ``None`` to use lower layers.
            cache_dir: Explicit cache directory, or ``None`` to use lower layers.
            log_level: Explicit log level, or ``None`` to use lower layers.
            offline: Explicit offline flag, or ``None`` to use lower layers.

        Returns:
            An immutable validated configuration snapshot.

        Raises:
            ConfigError: If the TOML file is unreadable or malformed, or a
                selected value is invalid.
        """
        toml_values = _load_toml_core()
        resolved_device = _resolve_device(device, toml_values)
        resolved_cache_dir = _resolve_cache_dir(cache_dir, toml_values)
        resolved_log_level = _resolve_log_level(log_level, toml_values)
        resolved_offline = _resolve_offline(offline, toml_values)
        return cls(
            device=resolved_device,
            cache_dir=resolved_cache_dir,
            log_level=resolved_log_level,
            offline=resolved_offline,
        )


def _config_path() -> Path:
    """Return the user configuration file path.

    Returns:
        ``~/.ceia-aisdk/config.toml`` under the current home directory.
    """
    return Path.home() / _CONFIG_DIRNAME / _CONFIG_FILENAME


def _load_toml_core() -> dict[str, object]:
    """Read the ``[core]`` table from the user TOML file.

    Returns:
        The ``core`` mapping, or an empty mapping when the file is missing or
        empty.

    Raises:
        ConfigError: If the file cannot be read or is not valid TOML.
    """
    path = _config_path()
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(
            "The configuration file is unreadable.",
            remediation=(
                "Fix permissions on ~/.ceia-aisdk/config.toml or remove the file "
                "and rely on environment variables or defaults."
            ),
        ) from exc
    if not text.strip():
        return {}
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(
            "The configuration file is malformed TOML.",
            remediation=(
                "Replace ~/.ceia-aisdk/config.toml with valid TOML containing an "
                "optional [core] table, or remove the file."
            ),
        ) from exc
    core = parsed.get("core", {})
    if core in ({}, None):
        return {}
    if not isinstance(core, dict):
        raise ConfigError(
            "The configuration file [core] section must be a table.",
            remediation="Use a [core] table with keys device, cache_dir, log_level, and offline.",
        )
    return core


def _present_env(name: str) -> bool:
    """Return whether an environment variable is present, including empty values.

    Args:
        name: Environment variable name.

    Returns:
        True when the variable is set in the process environment.
    """
    return name in os.environ


def _resolve_device(explicit: str | None, toml_values: dict[str, object]) -> str:
    """Resolve and validate the device field.

    Args:
        explicit: Explicit argument, if provided.
        toml_values: Parsed ``[core]`` table.

    Returns:
        The validated device string.

    Raises:
        ConfigError: If the winning value is invalid.
    """
    value, source = _pick(
        explicit=explicit,
        env_name="CEIA_AISDK_DEVICE",
        toml_values=toml_values,
        toml_key="device",
        default=_DEFAULT_DEVICE,
    )
    if not isinstance(value, str) or not _DEVICE_RE.fullmatch(value):
        raise ConfigError(
            f"The device {source} value is invalid.",
            remediation=(
                "Set device to auto, cpu, cuda, or cuda:N where N is a "
                "canonical nonnegative integer."
            ),
        )
    return value


def _resolve_cache_dir(
    explicit: str | os.PathLike[str] | None,
    toml_values: dict[str, object],
) -> Path:
    """Resolve and validate the cache directory field.

    Args:
        explicit: Explicit argument, if provided.
        toml_values: Parsed ``[core]`` table.

    Returns:
        The expanded cache directory path.

    Raises:
        ConfigError: If the winning value is empty, contains NUL, or cannot be
            expanded.
    """
    value, source = _pick(
        explicit=explicit,
        env_name="CEIA_AISDK_CACHE_DIR",
        toml_values=toml_values,
        toml_key="cache_dir",
        default=_DEFAULT_CACHE_DIR,
    )
    try:
        text = os.fsdecode(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            f"The cache_dir {source} value is invalid.",
            remediation="Set cache_dir to a nonempty path without NUL characters.",
        ) from exc
    if not text or "\x00" in text:
        raise ConfigError(
            f"The cache_dir {source} value is invalid.",
            remediation="Set cache_dir to a nonempty path without NUL characters.",
        )
    try:
        return Path(text).expanduser()
    except RuntimeError as exc:
        raise ConfigError(
            f"The cache_dir {source} value could not expand the home directory.",
            remediation="Set cache_dir to an absolute path or fix the HOME environment variable.",
        ) from exc


def _resolve_log_level(explicit: str | None, toml_values: dict[str, object]) -> str:
    """Resolve and validate the log level field.

    Args:
        explicit: Explicit argument, if provided.
        toml_values: Parsed ``[core]`` table.

    Returns:
        The validated log level name.

    Raises:
        ConfigError: If the winning value is not an exact accepted level.
    """
    value, source = _pick(
        explicit=explicit,
        env_name="CEIA_AISDK_LOG_LEVEL",
        toml_values=toml_values,
        toml_key="log_level",
        default=_DEFAULT_LOG_LEVEL,
    )
    if not isinstance(value, str) or value not in _LOG_LEVELS:
        raise ConfigError(
            f"The log_level {source} value is invalid.",
            remediation="Set log_level to exactly DEBUG, INFO, WARNING, ERROR, or CRITICAL.",
        )
    return value


def _resolve_offline(explicit: bool | None, toml_values: dict[str, object]) -> bool:
    """Resolve and validate the offline field.

    Args:
        explicit: Explicit argument, if provided.
        toml_values: Parsed ``[core]`` table.

    Returns:
        The validated offline flag.

    Raises:
        ConfigError: If the winning value is not a boolean or ``0``/``1``.
    """
    value, source = _pick(
        explicit=explicit,
        env_name="CEIA_AISDK_OFFLINE",
        toml_values=toml_values,
        toml_key="offline",
        default=_DEFAULT_OFFLINE,
    )
    if source == _SOURCE_ENVIRONMENT:
        if value == "0":
            return False
        if value == "1":
            return True
        raise ConfigError(
            "The offline environment value is invalid; accepted values are 0 or 1.",
            remediation="Set CEIA_AISDK_OFFLINE to 0 or 1.",
        )
    if isinstance(value, bool):
        return value
    raise ConfigError(
        f"The offline {source} value is invalid.",
        remediation="Set offline to a boolean in TOML or pass a boolean explicit argument.",
    )


def _pick(
    *,
    explicit: object,
    env_name: str,
    toml_values: dict[str, object],
    toml_key: str,
    default: object,
) -> tuple[object, str]:
    """Select the winning source for one field.

    Args:
        explicit: Explicit argument, or ``None`` when absent.
        env_name: Matching ``CEIA_AISDK_*`` variable.
        toml_values: Parsed ``[core]`` table.
        toml_key: Key inside ``[core]``.
        default: Field default.

    Returns:
        The winning value and a privacy-safe source label.
    """
    if explicit is not None:
        return explicit, _SOURCE_EXPLICIT
    if _present_env(env_name):
        return os.environ[env_name], _SOURCE_ENVIRONMENT
    if toml_key in toml_values:
        return toml_values[toml_key], _SOURCE_TOML
    _LOGGER.debug("Using default for %s", toml_key)
    return default, _SOURCE_DEFAULT
