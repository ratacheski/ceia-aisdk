"""Side-effect-safe logging helpers for the ``ceia_aisdk`` namespace.

This module never calls ``logging.basicConfig``, never mutates the root
logger, and never installs a console handler. Importing it is not enough
to change process-wide logging policy; callers must invoke the helpers
explicitly.
"""

from __future__ import annotations

import logging

_PACKAGE_LOGGER_NAME = "ceia_aisdk"


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``ceia_aisdk`` namespace.

    Args:
        name: Fully qualified logger name. It should start with
            ``ceia_aisdk``.

    Returns:
        The named logger instance.
    """
    return logging.getLogger(name)


def install_null_handler() -> None:
    """Install a ``NullHandler`` on the package logger if missing.

    The helper is idempotent and does not change the root logger or add a
    stream handler.
    """
    logger = logging.getLogger(_PACKAGE_LOGGER_NAME)
    if not any(isinstance(handler, logging.NullHandler) for handler in logger.handlers):
        logger.addHandler(logging.NullHandler())


def configure_namespace(level: str) -> None:
    """Set the ``ceia_aisdk`` namespace log level without touching root.

    Repeated calls are idempotent: they update the level and do not add
    extra handlers.

    Args:
        level: Logging level name such as ``DEBUG`` or ``WARNING``.

    Raises:
        ValueError: If ``level`` is not a recognized logging level name.
    """
    resolved = logging.getLevelName(level)
    if not isinstance(resolved, int):
        raise ValueError(f"Unsupported log level: {level!s}")
    install_null_handler()
    logging.getLogger(_PACKAGE_LOGGER_NAME).setLevel(resolved)
