"""CEIA AI SDK operational foundation for Linux x86_64.

The package root exposes version metadata and public error types without
importing the CLI, diagnostic renderers, or inference backends.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from ceia_aisdk._logging import install_null_handler
from ceia_aisdk.config import AISDKConfig
from ceia_aisdk.errors import (
    AISDKError,
    CapabilityError,
    ConfigError,
    DeviceError,
    DownloadError,
    GenerationError,
    ModelNotFoundError,
)
from ceia_aisdk.hardware import GPUInfo, detect_gpus, get_device

install_null_handler()

try:
    __version__ = version("ceia-aisdk")
except PackageNotFoundError:  # pragma: no cover - editable installs expose metadata
    __version__ = "0.1.0"

__all__ = [
    "AISDKConfig",
    "AISDKError",
    "CapabilityError",
    "ConfigError",
    "DeviceError",
    "DownloadError",
    "GPUInfo",
    "GenerationError",
    "ModelNotFoundError",
    "__version__",
    "detect_gpus",
    "get_device",
]
