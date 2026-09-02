"""Contract tests for ceia-aisdk model CLI help discovery."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Mapping

import pytest

_COMMAND = "ceia-aisdk"
_NON_ENGLISH_RE = re.compile(
    r"\b(não|diagnóstico|versão|ajuda|comando|erro|configuração)\b",
    re.IGNORECASE,
)
_MODEL_COMMANDS = ("pull", "list", "rm", "info", "verify", "where")


def _run(
    args: list[str], *, env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [_COMMAND, *args], capture_output=True, text=True, env=merged, check=False
    )


@pytest.fixture(scope="module")
def cli_available() -> str:
    path = shutil.which(_COMMAND)
    assert path, "ceia-aisdk console script is not available on PATH"
    return path


def test_root_help_lists_model(cli_available: str) -> None:
    del cli_available
    result = _run(["--help"])
    assert result.returncode == 0, result.stderr
    text = result.stdout
    assert "model" in text
    assert "doctor" in text
    assert "ceia-aisdk model --help" in text
    model_lines = [line for line in text.splitlines() if re.search(r"\bmodel\b", line)]
    assert any(re.search(r"model\s+\S+", line) for line in model_lines)
    assert _NON_ENGLISH_RE.search(text) is None


def test_model_help_lists_commands(cli_available: str) -> None:
    del cli_available
    result = _run(["model", "--help"])
    assert result.returncode == 0, result.stderr
    text = result.stdout
    for command in _MODEL_COMMANDS:
        assert re.search(rf"\b{command}\b", text), command
    assert "ceia-aisdk model pull llm/small" in text
    assert "opaque" in text.lower() or "alias" in text.lower()
    assert _NON_ENGLISH_RE.search(text) is None


def test_model_help_examples_are_not_executed_against_production(cli_available: str) -> None:
    del cli_available
    result = _run(["model", "--help"])
    assert result.returncode == 0
    assert "ceia-aisdk model pull llm/small" in result.stdout


def test_pull_help_covers_integrity_resume_and_essentials(cli_available: str) -> None:
    del cli_available
    result = _run(["model", "pull", "--help"])
    assert result.returncode == 0, result.stderr
    text = result.stdout.lower()
    assert "integrity" in text or "checksum" in text or "sha-256" in text
    assert "resume" in text
    assert "essentials" in text
    assert "cache" in text
    assert "package" in text
    assert "ceia-aisdk model pull llm/small" in result.stdout
    assert "ceia-aisdk model pull --essentials" in result.stdout
    assert _NON_ENGLISH_RE.search(result.stdout) is None


def test_where_and_verify_help_include_examples(cli_available: str) -> None:
    del cli_available
    where = _run(["model", "where", "--help"])
    verify = _run(["model", "verify", "--help"])
    assert where.returncode == 0, where.stderr
    assert verify.returncode == 0, verify.stderr
    assert "ceia-aisdk model where llm/small" in where.stdout
    assert "ceia-aisdk model verify" in verify.stdout
    assert _NON_ENGLISH_RE.search(where.stdout) is None
    assert _NON_ENGLISH_RE.search(verify.stdout) is None


def test_info_help_states_unsigned_catalog_and_checksum_integrity(cli_available: str) -> None:
    del cli_available
    result = _run(["model", "info", "--help"])
    assert result.returncode == 0, result.stderr
    text = result.stdout.lower()
    assert "authenticity" in text or "unsigned" in text or "not verified" in text
    assert "checksum" in text or "sha-256" in text or "integrity" in text
    assert "ceia-aisdk model info llm/small" in result.stdout
    assert _NON_ENGLISH_RE.search(result.stdout) is None


def test_essentials_help_and_example(cli_available: str) -> None:
    del cli_available
    result = _run(["model", "pull", "--help"])
    assert result.returncode == 0
    assert "--essentials" in result.stdout
    assert "ceia-aisdk model pull --essentials" in result.stdout


def test_list_and_rm_help_include_examples(cli_available: str) -> None:
    del cli_available
    listed = _run(["model", "list", "--help"])
    removed = _run(["model", "rm", "--help"])
    assert listed.returncode == 0, listed.stderr
    assert removed.returncode == 0, removed.stderr
    assert "ceia-aisdk model list" in listed.stdout
    assert "ceia-aisdk model rm llm/small" in removed.stdout
