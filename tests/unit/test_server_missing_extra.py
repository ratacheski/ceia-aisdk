"""Unit tests for the missing ``[server]`` extra start path."""

from __future__ import annotations

import builtins

import pytest
from typer.testing import CliRunner

from ceia_aisdk.cli import app

runner = CliRunner()


def test_serve_missing_extra_exits_one_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def _guarded(name: str, *args: object, **kwargs: object) -> object:
        if name == "fastapi" or name.startswith("fastapi.") or name.startswith("ceia_aisdk.server"):
            raise ImportError("No module named 'fastapi'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _guarded)
    result = runner.invoke(app, ["serve"])
    blob = f"{result.stdout}{result.stderr}{result.output}"
    assert result.exit_code == 1, blob
    assert "Traceback" not in blob
    assert "ceia-aisdk[server]" in blob


def test_serve_help_still_works_when_extra_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def _guarded(name: str, *args: object, **kwargs: object) -> object:
        if name == "fastapi" or name.startswith("fastapi.") or name.startswith("ceia_aisdk.server"):
            raise ImportError("No module named 'fastapi'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _guarded)
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    assert "--host" in result.output
