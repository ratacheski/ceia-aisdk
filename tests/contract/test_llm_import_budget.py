"""Contract tests that LLM imports stay free of llama_cpp."""

from __future__ import annotations

import subprocess
import sys


def test_package_root_import_does_not_load_llama_cpp() -> None:
    code = """
import sys
import ceia_aisdk
assert 'llama_cpp' not in sys.modules, sorted(sys.modules)
assert ceia_aisdk.__version__
from ceia_aisdk import GenerationError, CapabilityError
assert issubclass(GenerationError, ceia_aisdk.AISDKError)
assert issubclass(CapabilityError, ceia_aisdk.AISDKError)
"""
    result = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_importing_llm_settings_does_not_load_llama_cpp() -> None:
    code = """
import sys
from ceia_aisdk.llm import LLMSettings
assert 'llama_cpp' not in sys.modules, sorted(sys.modules)
assert LLMSettings.load().default_alias == 'llm/small@latest'
"""
    result = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_importing_llm_type_does_not_load_llama_cpp() -> None:
    code = """
import sys
from ceia_aisdk.llm import (
    LLM, AsyncLLM, Session, LLMSettings, ToolDeclaration, ToolCall, CompletionResult,
)
assert 'llama_cpp' not in sys.modules, sorted(sys.modules)
assert LLM is not None
assert AsyncLLM is not None
assert Session is not None
assert LLMSettings is not None
assert ToolDeclaration is not None
assert ToolCall is not None
assert CompletionResult is not None
"""
    result = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
