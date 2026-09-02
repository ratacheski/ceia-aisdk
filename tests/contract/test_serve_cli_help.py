"""Contract tests for ``ceia-aisdk serve`` help discovery and completeness."""

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
_NON_ENGLISH_RE = re.compile(
    r"\b(não|diagnóstico|versão|ajuda|comando|erro|configuração)\b",
    re.IGNORECASE,
)


def _run(
    args: list[str], *, env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [_COMMAND, *args], capture_output=True, text=True, env=merged, check=False
    )


def _is_long_running_serve(example: str) -> bool:
    command = example
    while True:
        match = re.match(r"^([A-Z][A-Z0-9_]*)=(\S+)\s+(.*)$", command)
        if not match:
            break
        command = match.group(3)
    tokens = command.split()
    if len(tokens) < 2 or tokens[0] != _COMMAND or tokens[1] != "serve":
        return False
    return "--help" not in tokens and "-h" not in tokens


@pytest.fixture(scope="module")
def cli_available() -> str:
    path = shutil.which(_COMMAND)
    assert path, "ceia-aisdk console script is not available on PATH"
    return path


def test_root_help_lists_serve_with_short_help(cli_available: str) -> None:
    del cli_available
    result = _run(["--help"])
    assert result.returncode == 0, result.stderr
    text = result.stdout
    assert "serve" in text
    serve_lines = [line for line in text.splitlines() if re.search(r"\bserve\b", line)]
    assert serve_lines
    assert any(re.search(r"serve\s+\S+", line) for line in serve_lines), serve_lines
    assert _NON_ENGLISH_RE.search(text) is None


def test_serve_help_works_without_starting_the_server(cli_available: str) -> None:
    del cli_available
    result = _run(["serve", "--help"])
    assert result.returncode == 0, result.stderr
    text = result.stdout
    assert "OpenAI" in text or "openai" in text.lower()
    assert "Linux x86_64" in text
    assert "/v1" in text
    assert "opaque" in text.lower() or "alias" in text.lower()
    assert "--host" in text
    assert "--port" in text
    assert "--token" in text
    assert "--cors" in text
    assert "--debug" in text
    assert "127.0.0.1" in text
    assert "11434" in text
    assert "ceia-aisdk[server]" in text or "[server]" in text
    assert "0.0.0.0" in text
    assert "reverse proxy" in text.lower() or "tls" in text.lower()
    assert "ceia-aisdk serve --help" in text
    assert _NON_ENGLISH_RE.search(text) is None


def test_serve_help_example_is_executable(cli_available: str) -> None:
    del cli_available
    result = _run(["serve", "--help"])
    assert result.returncode == 0, result.stderr
    examples: list[str] = []
    in_examples = False
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip().lstrip("$ ").strip()
        if line.lower().startswith("example"):
            in_examples = True
            continue
        if in_examples and _EXAMPLE_RE.match(line):
            examples.append(line)
    assert any(item == "ceia-aisdk serve --help" for item in examples), examples
    help_example = _run(["serve", "--help"])
    assert help_example.returncode == 0


def test_example_harvester_skips_long_running_serve(cli_available: str) -> None:
    del cli_available
    assert _is_long_running_serve("ceia-aisdk serve")
    assert _is_long_running_serve("ceia-aisdk serve --host 127.0.0.1 --port 11434")
    assert not _is_long_running_serve("ceia-aisdk serve --help")
    assert not _is_long_running_serve("ceia-aisdk doctor")
