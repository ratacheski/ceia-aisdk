"""Contract tests for root and doctor CLI help."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Mapping

import pytest

_COMMAND = "ceia-aisdk"
_EXAMPLE_RE = re.compile(
    r"^(?:[A-Z][A-Z0-9_]*=\S+\s+)*ceia-aisdk(?:\s+\S+)*$",
)
# Portuguese tokens below are fixtures that detect non-English CLI leakage.
_NON_ENGLISH_RE = re.compile(
    r"\b(não|diagnóstico|versão|ajuda|comando|erro|configuração)\b",
    re.IGNORECASE,
)


def _run(
    args: list[str], *, env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    command = [_COMMAND, *args]
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(command, capture_output=True, text=True, env=merged, check=False)


@pytest.fixture(scope="module")
def cli_available() -> str:
    path = shutil.which(_COMMAND)
    assert path, "ceia-aisdk console script is not available on PATH"
    return path


def test_root_help_lists_doctor_and_examples(cli_available: str) -> None:
    del cli_available
    result = _run(["--help"])
    assert result.returncode == 0, result.stderr
    text = result.stdout
    assert "Linux x86_64" in text
    assert "doctor" in text
    assert "Examples" in text
    assert "ceia-aisdk doctor" in text
    assert "download" in text.lower() or "foundation" in text.lower()
    assert _NON_ENGLISH_RE.search(text) is None


def test_doctor_is_discoverable_with_short_help(cli_available: str) -> None:
    del cli_available
    result = _run(["--help"])
    assert result.returncode == 0
    doctor_lines = [line for line in result.stdout.splitlines() if re.search(r"\bdoctor\b", line)]
    assert doctor_lines
    short_help = doctor_lines[-1]
    assert re.search(r"doctor\s+\S+", short_help), short_help


def test_doctor_help_covers_scope_and_examples(cli_available: str) -> None:
    del cli_available
    result = _run(["doctor", "--help"])
    assert result.returncode == 0, result.stderr
    text = result.stdout
    assert "download" in text.lower()
    assert "Linux x86_64" in text
    assert "CUDA" in text or "cuda" in text
    assert "ceia-aisdk doctor" in text
    assert "CEIA_AISDK_DEVICE=cpu" in text
    assert "Examples" in text
    assert _NON_ENGLISH_RE.search(text) is None


def test_help_examples_are_executable(cli_available: str) -> None:
    del cli_available
    pages = [_run(["--help"]).stdout, _run(["doctor", "--help"]).stdout]
    examples: list[str] = []
    for page in pages:
        in_examples = False
        for raw_line in page.splitlines():
            line = raw_line.strip().lstrip("$ ").strip()
            if line.lower().startswith("example"):
                in_examples = True
                continue
            if in_examples and _EXAMPLE_RE.match(line):
                examples.append(line)
    unique_examples = list(dict.fromkeys(examples))
    assert unique_examples, "help pages must include executable ceia-aisdk examples"
    assert any(item == "ceia-aisdk doctor" or item.endswith(" doctor") for item in unique_examples)
    for example in unique_examples:
        env: dict[str, str] = {}
        command = example
        while True:
            match = re.match(r"^([A-Z][A-Z0-9_]*)=(\S+)\s+(.*)$", command)
            if not match:
                break
            env[match.group(1)] = match.group(2)
            command = match.group(3)
        args = command.split()
        assert args[0] == _COMMAND
        result = _run(args[1:], env=env)
        assert result.returncode in {0, 1}, (
            f"{example!r} exited {result.returncode}: {result.stderr}"
        )
