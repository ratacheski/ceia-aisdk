"""Layered ``[llm]`` settings loaded beside ``AISDKConfig``."""

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
_DEFAULT_ALIAS = "llm/small@latest"
_DEFAULT_CONTEXT_LENGTH = 8192
_SOURCE_EXPLICIT = "explicit argument"
_SOURCE_ENVIRONMENT = "environment"
_SOURCE_TOML = "configuration file"
_SOURCE_DEFAULT = "default"
_ENV_INT_RE: Final = r"^\+?[1-9][0-9]*$"


@dataclass(frozen=True, slots=True)
class LLMSettings:
    """Effective, validated LLM launch settings.

    Attributes:
        default_alias: Canonical or size-only alias used when ``LLM()``
            receives no alias. Defaults to ``llm/small@latest``.
        context_length: Positive generation context window. Defaults to
            ``8192``.
    """

    default_alias: str
    context_length: int

    @classmethod
    def load(
        cls,
        *,
        default_alias: str | None = None,
        context_length: int | None = None,
    ) -> LLMSettings:
        """Load ``[llm]`` settings from arguments, environment, TOML, and defaults.

        Each field is resolved independently. A missing ``[llm]`` table is
        equivalent to defaults. Loading does not construct a model or import
        ``llama_cpp``.

        Args:
            default_alias: Explicit alias override, or ``None`` to use lower
                layers.
            context_length: Explicit context window, or ``None`` to use lower
                layers.

        Returns:
            An immutable validated settings snapshot.

        Raises:
            ConfigError: If the TOML file is unreadable or malformed, or a
                selected value is invalid.
        """
        toml_values = _load_toml_llm()
        resolved_alias = _resolve_default_alias(default_alias, toml_values)
        resolved_context = _resolve_context_length(context_length, toml_values)
        return cls(default_alias=resolved_alias, context_length=resolved_context)


def _config_path() -> Path:
    """Return the user configuration file path.

    Returns:
        ``~/.ceia-aisdk/config.toml`` under the current home directory.
    """
    return Path.home() / _CONFIG_DIRNAME / _CONFIG_FILENAME


def _load_toml_llm() -> dict[str, object]:
    """Read the ``[llm]`` table from the user TOML file.

    Returns:
        The ``llm`` mapping, or an empty mapping when the file or table is
        missing.

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
                "optional [llm] table, or remove the file."
            ),
        ) from exc
    table = parsed.get("llm", {})
    if table in ({}, None):
        return {}
    if not isinstance(table, dict):
        raise ConfigError(
            "The configuration file [llm] section must be a table.",
            remediation="Use an [llm] table with keys default_alias and context_length.",
        )
    return table


def _present_env(name: str) -> bool:
    """Return whether an environment variable is present, including empty values.

    Args:
        name: Environment variable name.

    Returns:
        True when the variable is set in the process environment.
    """
    return name in os.environ


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
        env_name: Matching ``CEIA_AISDK_LLM_*`` variable.
        toml_values: Parsed ``[llm]`` table.
        toml_key: Key inside ``[llm]``.
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


def _resolve_default_alias(explicit: str | None, toml_values: dict[str, object]) -> str:
    """Resolve and validate the default alias.

    Args:
        explicit: Explicit argument, if provided.
        toml_values: Parsed ``[llm]`` table.

    Returns:
        The validated alias string.

    Raises:
        ConfigError: If the winning value is empty or not a string.
    """
    value, source = _pick(
        explicit=explicit,
        env_name="CEIA_AISDK_LLM_DEFAULT_ALIAS",
        toml_values=toml_values,
        toml_key="default_alias",
        default=_DEFAULT_ALIAS,
    )
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(
            f"The default_alias {source} value is invalid.",
            remediation=(
                "Set [llm] default_alias to a nonempty catalog alias such as "
                "llm/small@latest or medium."
            ),
        )
    return value.strip()


def _resolve_context_length(explicit: int | None, toml_values: dict[str, object]) -> int:
    """Resolve and validate the context length.

    Args:
        explicit: Explicit argument, if provided.
        toml_values: Parsed ``[llm]`` table.

    Returns:
        A positive integer context window.

    Raises:
        ConfigError: If the winning value is not a positive integer.
    """
    value, source = _pick(
        explicit=explicit,
        env_name="CEIA_AISDK_LLM_CONTEXT_LENGTH",
        toml_values=toml_values,
        toml_key="context_length",
        default=_DEFAULT_CONTEXT_LENGTH,
    )
    if source == _SOURCE_ENVIRONMENT:
        if not isinstance(value, str) or re.fullmatch(_ENV_INT_RE, value) is None:
            raise ConfigError(
                "The context_length environment value is invalid.",
                remediation=(
                    "Set CEIA_AISDK_LLM_CONTEXT_LENGTH to a positive base-10 integer such as 8192."
                ),
            )
        return int(value)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError(
            f"The context_length {source} value is invalid.",
            remediation="Set [llm] context_length to a positive integer such as 8192.",
        )
    return value
