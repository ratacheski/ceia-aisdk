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


class ModelNotFoundError(AISDKError):
    """Raised when a cataloged alias is not present in the active catalog."""

    def __init__(self, message: str, *, remediation: str) -> None:
        """Initialize a missing-alias error.

        Args:
            message: Nonempty user-facing English explanation.
            remediation: Nonempty user-facing English next action. When the
                domain is known, list aliases available in that domain.
        """
        super().__init__(message, remediation=remediation)


class DownloadError(AISDKError):
    """Raised when a catalog load, transfer, integrity check, or cache write fails."""

    def __init__(self, message: str, *, remediation: str) -> None:
        """Initialize a download or catalog-load error.

        Args:
            message: Nonempty user-facing English explanation. Must not include
                catalog origin URLs or upstream filenames.
            remediation: Nonempty user-facing English next action. Must not
                include catalog origin URLs.
        """
        super().__init__(message, remediation=remediation)


class GenerationError(AISDKError):
    """Raised when local generation or model load fails."""

    def __init__(self, message: str, *, remediation: str) -> None:
        """Initialize a generation or load error.

        Args:
            message: Nonempty user-facing English explanation. Must not include
                catalog origin URLs, prompt text, or completion bodies.
            remediation: Nonempty user-facing English next action, such as
                shortening session history or raising context_length.
        """
        super().__init__(message, remediation=remediation)


class CapabilityError(AISDKError):
    """Raised when a requested capability is not supported by the alias."""

    def __init__(self, message: str, *, remediation: str) -> None:
        """Initialize a missing-capability error.

        Args:
            message: Nonempty user-facing English explanation.
            remediation: Nonempty user-facing English next action, such as
                choosing an alias whose capabilities include tool_use.
        """
        super().__init__(message, remediation=remediation)
