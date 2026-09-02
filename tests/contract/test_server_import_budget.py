"""Contract tests that package import stays free of the serving stack."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import ceia_aisdk


def _imported_top_level_names(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
            elif node.level == 1:
                names.update(alias.name.split(".")[0] for alias in node.names)
                if node.module:
                    names.add(node.module.split(".")[0])
    return names


def test_package_root_source_does_not_import_server_or_http_stack() -> None:
    init_path = Path(ceia_aisdk.__file__).resolve()
    imported = _imported_top_level_names(init_path.read_text(encoding="utf-8"))
    assert "fastapi" not in imported
    assert "uvicorn" not in imported
    assert "server" not in imported


def test_fresh_import_leaves_fastapi_uvicorn_and_server_unloaded() -> None:
    code = """
import sys
import ceia_aisdk
assert ceia_aisdk.__version__
assert 'fastapi' not in sys.modules
assert 'uvicorn' not in sys.modules
assert 'ceia_aisdk.server' not in sys.modules
from ceia_aisdk import ServerError
assert issubclass(ServerError, ceia_aisdk.AISDKError)
assert 'fastapi' not in sys.modules
assert 'uvicorn' not in sys.modules
assert 'ceia_aisdk.server' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr or result.stdout
