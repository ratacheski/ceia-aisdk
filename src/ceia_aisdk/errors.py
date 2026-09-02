"""Public error hierarchy for the CEIA AI SDK.

Every public failure exposes a nonempty English message and a nonempty
remediation string describing the next action.
"""

from __future__ import annotations


class AISDKError(Exception):
    """Root public exception for CEIA AI SDK failures."""

    remediation: str

    def __init__(self, message: str, *, remediation: str) -> None:
        """Initialize a public SDK error.

        Args:
            message: Nonempty user-facing English explanation.
            remediation: Nonempty user-facing English next action.

        Raises:
            ValueError: If ``message`` or ``remediation`` is empty or whitespace.
        """
        if not isinstance(message, str) or not message.strip():
            raise ValueError("AISDKError message must be nonempty English text")
        if not isinstance(remediation, str) or not remediation.strip():
            raise ValueError("AISDKError remediation must be nonempty English text")
        super().__init__(message)
        self.remediation = remediation


class ConfigError(AISDKError):
    """Raised when effective configuration is invalid or unreadable."""

    def __init__(self, message: str, *, remediation: str) -> None:
        """Initialize a configuration error.

        Args:
            message: Nonempty user-facing English explanation.
            remediation: Nonempty user-facing English next action.
        """
        super().__init__(message, remediation=remediation)


class DeviceError(AISDKError):
    """Raised when an explicitly requested compute device cannot be selected."""

    def __init__(self, message: str, *, remediation: str) -> None:
        """Initialize a device-selection error.

        Args:
            message: Nonempty user-facing English explanation.
            remediation: Nonempty user-facing English next action.
        """
        super().__init__(message, remediation=remediation)
