"""Unit tests for namespaced, side-effect-safe SDK logging."""

from __future__ import annotations

import logging

from ceia_aisdk import _logging


def _root_snapshot() -> tuple[int, list[logging.Handler]]:
    root = logging.getLogger()
    return root.level, list(root.handlers)


def test_package_logger_is_namespaced() -> None:
    logger = _logging.get_logger("ceia_aisdk.config")
    assert logger.name == "ceia_aisdk.config"
    assert logger.name.startswith("ceia_aisdk")


def test_null_handler_is_installed_without_console_handler() -> None:
    _logging.install_null_handler()
    package_logger = logging.getLogger("ceia_aisdk")
    assert any(isinstance(handler, logging.NullHandler) for handler in package_logger.handlers)
    assert not any(
        isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.NullHandler)
        for handler in package_logger.handlers
    )


def test_configuration_does_not_mutate_root_logger() -> None:
    before_level, before_handlers = _root_snapshot()
    _logging.install_null_handler()
    _logging.configure_namespace("DEBUG")
    after_level, after_handlers = _root_snapshot()
    assert after_level == before_level
    assert after_handlers == before_handlers
    assert logging.getLogger("ceia_aisdk").level == logging.DEBUG


def test_namespace_configuration_is_idempotent() -> None:
    _logging.install_null_handler()
    first_count = len(logging.getLogger("ceia_aisdk").handlers)
    _logging.configure_namespace("INFO")
    _logging.configure_namespace("INFO")
    _logging.install_null_handler()
    package_logger = logging.getLogger("ceia_aisdk")
    null_handlers = [
        handler for handler in package_logger.handlers if isinstance(handler, logging.NullHandler)
    ]
    assert len(null_handlers) == 1
    assert len(package_logger.handlers) == first_count
    assert package_logger.level == logging.INFO


def test_module_and_helpers_have_english_docstrings() -> None:
    assert _logging.__doc__
    assert _logging.install_null_handler.__doc__
    assert _logging.configure_namespace.__doc__
    assert _logging.get_logger.__doc__
    assert "root" in (_logging.install_null_handler.__doc__ or "").lower() or "NullHandler" in (
        _logging.install_null_handler.__doc__ or ""
    )
