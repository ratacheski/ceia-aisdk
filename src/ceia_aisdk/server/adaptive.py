"""Reserved embeddings, audio, and vision gates for modules not in this slice.

Absent modules return stable HTTP refusals. These routes must not block the
``0.2.0`` chat and tools gate.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def register_adaptive_routes(app: FastAPI) -> None:
    """Register reserved module routes that return 501 while modules are absent.

    Args:
        app: FastAPI application created by ``create_app``.
    """

    @app.post("/v1/embeddings", response_model=None)
    async def embeddings(_request: Request) -> JSONResponse:
        """Refuse embeddings until the RAG module ships.

        Args:
            _request: Incoming request. The body is ignored.

        Returns:
            A 501 JSON envelope.
        """
        return _not_implemented("embeddings")

    @app.post("/v1/audio/transcriptions", response_model=None)
    async def transcriptions(_request: Request) -> JSONResponse:
        """Refuse audio transcription until the voice module ships.

        Args:
            _request: Incoming request. The body is ignored.

        Returns:
            A 501 JSON envelope.
        """
        return _not_implemented("audio transcription")

    @app.post("/v1/audio/speech", response_model=None)
    async def speech(_request: Request) -> JSONResponse:
        """Refuse speech synthesis until the voice module ships.

        Args:
            _request: Incoming request. The body is ignored.

        Returns:
            A 501 JSON envelope.
        """
        return _not_implemented("speech synthesis")


def _not_implemented(feature: str) -> JSONResponse:
    """Return the reserved-route 501 envelope.

    Args:
        feature: English feature name used in the message.

    Returns:
        A JSON response with ``not_implemented_error``.
    """
    from ceia_aisdk.server.app import error_envelope

    return error_envelope(
        message=f"{feature} is not available in this release.",
        error_type="not_implemented_error",
        remediation="Use /v1/chat/completions for text. Voice, vision, and RAG ship later.",
        status_code=501,
    )
