"""Contract tests for package identity, version, and import surface."""

from __future__ import annotations

import ast
import dataclasses
import importlib.metadata
import inspect
import logging
import subprocess
import sys
from pathlib import Path

import pytest

import ceia_aisdk
from ceia_aisdk import AISDKConfig

_FORBIDDEN_ROOT_IMPORTS = {
    "typer",
    "rich",
    "httpx",
    "yaml",
    "torch",
    "llama_cpp",
    "faster_whisper",
    "piper",
}


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


def test_distribution_name_is_ceia_aisdk() -> None:
    dist = importlib.metadata.distribution("ceia-aisdk")
    assert dist.metadata["Name"] == "ceia-aisdk"


def test_version_matches_installed_metadata() -> None:
    metadata_version = importlib.metadata.version("ceia-aisdk")
    assert ceia_aisdk.__version__ == metadata_version
    assert ceia_aisdk.__version__


def test_public_error_exports() -> None:
    assert ceia_aisdk.AISDKError is not None
    assert ceia_aisdk.ConfigError is not None
    assert ceia_aisdk.DeviceError is not None
    assert ceia_aisdk.ModelNotFoundError is not None
    assert ceia_aisdk.DownloadError is not None
    assert ceia_aisdk.GenerationError is not None
    assert ceia_aisdk.CapabilityError is not None
    from ceia_aisdk import (
        AISDKError,
        CapabilityError,
        ConfigError,
        DeviceError,
        DownloadError,
        GenerationError,
        ModelNotFoundError,
    )

    assert issubclass(ConfigError, AISDKError)
    assert issubclass(DeviceError, AISDKError)
    assert issubclass(ModelNotFoundError, AISDKError)
    assert issubclass(DownloadError, AISDKError)
    assert issubclass(GenerationError, AISDKError)
    assert issubclass(CapabilityError, AISDKError)


def test_python_requires_range() -> None:
    requires = importlib.metadata.metadata("ceia-aisdk")["Requires-Python"]
    assert requires.replace(" ", "") == ">=3.11,<3.14"


def test_linux_classifier_without_windows_support() -> None:
    classifiers = importlib.metadata.metadata("ceia-aisdk").get_all("Classifier") or []
    assert "Operating System :: POSIX :: Linux" in classifiers
    assert not any("Microsoft :: Windows" in item for item in classifiers)
    assert not any("MacOS" in item for item in classifiers)


def test_cuda_extra_is_declared() -> None:
    dist = importlib.metadata.distribution("ceia-aisdk")
    extras = dist.metadata.get_all("Provides-Extra") or []
    assert "cuda" in extras
    assert "server" not in extras
    assert "apps" not in extras
    requires = dist.metadata.get_all("Requires-Dist") or []
    cuda_reqs = [
        item for item in requires if 'extra == "cuda"' in item or "extra == 'cuda'" in item
    ]
    assert cuda_reqs
    assert any("llama-cpp-python" in item for item in cuda_reqs)


def test_package_root_is_lightweight() -> None:
    init_path = Path(ceia_aisdk.__file__).resolve()
    imported = _imported_top_level_names(init_path.read_text(encoding="utf-8"))
    assert not (imported & _FORBIDDEN_ROOT_IMPORTS)
    assert "cli" not in imported
    assert "_diagnostics" not in imported
    assert "registry" not in imported
    assert "llm" not in imported


def test_fresh_import_does_not_load_cli_or_backends() -> None:
    code = """
import sys
import ceia_aisdk
forbidden = (
    "typer",
    "rich",
    "httpx",
    "yaml",
    "ceia_aisdk.cli",
    "ceia_aisdk.registry",
    "ceia_aisdk.llm",
    "ceia_aisdk._diagnostics",
    "torch",
    "llama_cpp",
    "faster_whisper",
    "piper",
)
loaded = [name for name in forbidden if name in sys.modules]
assert ceia_aisdk.__version__
assert not loaded, loaded
"""
    result = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_config_is_exported_immutable_and_slotted() -> None:
    assert AISDKConfig is ceia_aisdk.AISDKConfig
    assert dataclasses.is_dataclass(AISDKConfig)
    config = AISDKConfig.load()
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        config.device = "cpu"  # type: ignore[misc]
    assert getattr(AISDKConfig, "__slots__", None) is not None


def test_config_load_signature_is_keyword_only() -> None:
    signature = inspect.signature(AISDKConfig.load)
    parameters = signature.parameters
    for name in ("device", "cache_dir", "log_level", "offline"):
        assert name in parameters
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert parameters[name].default is None


def test_config_load_has_no_cli_or_hardware_side_effects(isolated_home: Path) -> None:
    del isolated_home
    root = logging.getLogger()
    before = (root.level, list(root.handlers))
    before_modules = set(sys.modules)
    config = AISDKConfig.load()
    added = set(sys.modules) - before_modules
    assert config.cache_dir.name == ".ceia-aisdk"
    assert (root.level, list(root.handlers)) == before
    assert "ceia_aisdk.cli" not in added
    assert "typer" not in added
    assert "rich" not in added
    assert "ceia_aisdk.hardware" not in added


def test_hardware_api_is_exported_immutable_and_documented() -> None:
    from ceia_aisdk import GPUInfo, detect_gpus, get_device

    assert GPUInfo is ceia_aisdk.GPUInfo
    assert detect_gpus is ceia_aisdk.detect_gpus
    assert get_device is ceia_aisdk.get_device
    assert dataclasses.is_dataclass(GPUInfo)
    gpu = GPUInfo(index=0, name="NVIDIA Test", total_vram_mib=1024, free_vram_mib=512)
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        gpu.name = "nope"  # type: ignore[misc]
    signature = inspect.signature(get_device)
    assert signature.parameters["device"].default == "auto"
    assert inspect.signature(detect_gpus).return_annotation
    assert GPUInfo.__doc__
    assert detect_gpus.__doc__
    assert get_device.__doc__


def test_package_import_does_not_probe_hardware() -> None:
    code = """
import sys
import ceia_aisdk
assert ceia_aisdk.GPUInfo
assert callable(ceia_aisdk.detect_gpus)
assert callable(ceia_aisdk.get_device)
assert "typer" not in sys.modules
assert "rich" not in sys.modules
assert "httpx" not in sys.modules
assert "yaml" not in sys.modules
assert "ceia_aisdk.cli" not in sys.modules
assert "ceia_aisdk.registry" not in sys.modules
assert "ceia_aisdk.llm" not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
