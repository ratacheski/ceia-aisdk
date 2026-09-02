"""FastAPI application factory for the OpenAI-compatible local server.

Constructing the app must not bind a socket, construct an ``LLM``, or import
``llama_cpp``. Binding is the CLI and uvicorn responsibility.
"""

from __future__ import annotations

import hmac
from typing import Any

try:
    from fastapi import FastAPI, Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException
    from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
    from starlette.requests import Request as StarletteRequest
    from starlette.responses import Response
except ImportError as exc:  # pragma: no cover - exercised by missing-extra tests
    from ceia_aisdk.errors import ServerError

    raise ServerError(
        "The OpenAI-compatible server extra is not installed.",
        remediation=(
            'Install the extra with pip install "ceia-aisdk[server]" '
            "(or uv sync --extra server for contributors) and retry."
        ),
    ) from exc

from ceia_aisdk.errors import (
    AISDKError,
    CapabilityError,
    DeviceError,
    DownloadError,
    GenerationError,
    ModelNotFoundError,
)
from ceia_aisdk.server.adaptive import register_adaptive_routes
from ceia_aisdk.server.messages import RequestValidationFailure
from ceia_aisdk.server.openai_compat import register_openai_routes
from ceia_aisdk.server.pool import ModelPool

GENERIC_REMEDIATION = "Retry the request, or inspect ceia-aisdk serve --help and the /v1 contract."


def error_envelope(
    *,
    message: str,
    error_type: str,
    remediation: str,
    code: str | None = None,
    status_code: int = 400,
) -> JSONResponse:
    """Return the stable OpenAI-shaped JSON error envelope.

    Args:
        message: English explanation. Must not include a traceback or prompt.
        error_type: Machine-readable error type.
        remediation: Nonempty next action.
        code: Optional machine-readable code.
        status_code: HTTP status to attach to the response.

    Returns:
        A JSON response with the ``error`` object required by the HTTP contract.
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": error_type,
                "code": code,
                "remediation": remediation,
            }
        },
    )


def create_app(
    *,
    token: str | None = None,
    cors_open: bool = False,
    debug: bool = False,
    pool: ModelPool | None = None,
) -> Any:
    """Build the ASGI application without binding a socket or loading a model.

    Args:
        token: Optional shared secret. When set, Bearer auth is required.
        cors_open: When true, allow any origin. Default is localhost-only CORS.
        debug: When true, DEBUG logs may include message bodies.
        pool: Optional model pool. Tests may inject a stub. The default pool
            constructs ``LLM`` instances on first chat.

    Returns:
        A FastAPI application object usable as an ASGI app.

    Raises:
        ServerError: If FastAPI cannot be imported because the ``[server]``
            extra is missing.
    """
    app = FastAPI(
        title="CEIA AI SDK OpenAI-compatible server",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.debug = debug
    app.state.token = token
    app.state.cors_open = cors_open
    app.state.pool = pool if pool is not None else ModelPool()
    _install_error_handlers(app)
    register_openai_routes(app)
    register_adaptive_routes(app)
    _install_auth_and_cors(app, token=token, cors_open=cors_open)
    return app


def _install_auth_and_cors(app: FastAPI, *, token: str | None, cors_open: bool) -> None:
    """Install optional Bearer auth and CORS policy.

    Args:
        app: FastAPI application being constructed.
        token: Shared secret, or ``None`` to disable auth.
        cors_open: When true, allow any origin without credentials.
    """
    app.add_middleware(BearerAuthMiddleware)
    if cors_open:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Reject ``/v1`` requests that lack a matching Bearer token when configured."""

    async def dispatch(
        self, request: StarletteRequest, call_next: RequestResponseEndpoint
    ) -> Response:
        """Compare Bearer tokens in constant time when a secret is set.

        Args:
            request: Incoming HTTP request.
            call_next: Next ASGI handler.

        Returns:
            The downstream response, or a 401 JSON envelope.
        """
        expected = getattr(request.app.state, "token", None)
        if expected is None or not request.url.path.startswith("/v1"):
            return await call_next(request)
        header = request.headers.get("authorization", "")
        scheme, _, remainder = header.partition(" ")
        provided = remainder if scheme.lower() == "bearer" else ""
        if not _tokens_match(expected, provided):
            return error_envelope(
                message="Missing or invalid Bearer token.",
                error_type="invalid_api_key",
                code="invalid_api_key",
                remediation="Send Authorization: Bearer <token> matching --token.",
                status_code=401,
            )
        return await call_next(request)


def _tokens_match(expected: str, provided: str) -> bool:
    """Compare secrets without leaking length through compare_digest.

    Args:
        expected: Configured shared secret.
        provided: Token from the Authorization header.

    Returns:
        True when the values are equal.
    """
    if len(expected) != len(provided):
        return False
    return hmac.compare_digest(expected.encode("utf-8"), provided.encode("utf-8"))


def _install_error_handlers(app: FastAPI) -> None:
    """Register stable JSON handlers for HTTP and SDK failures.

    Args:
        app: FastAPI application being constructed.
    """

    @app.exception_handler(RequestValidationFailure)
    async def _request_validation(_request: Request, exc: RequestValidationFailure) -> JSONResponse:
        return error_envelope(
            message=str(exc),
            error_type=exc.error_type,
            remediation=exc.remediation,
            status_code=exc.status_code,
        )

    @app.exception_handler(ModelNotFoundError)
    async def _missing_model(_request: Request, exc: ModelNotFoundError) -> JSONResponse:
        return error_envelope(
            message=str(exc),
            error_type="not_found_error",
            remediation=exc.remediation,
            status_code=404,
        )

    @app.exception_handler(DownloadError)
    async def _download(_request: Request, exc: DownloadError) -> JSONResponse:
        return error_envelope(
            message=str(exc),
            error_type="download_error",
            remediation=exc.remediation,
            status_code=503,
        )

    @app.exception_handler(DeviceError)
    async def _device(_request: Request, exc: DeviceError) -> JSONResponse:
        return error_envelope(
            message=str(exc),
            error_type="device_error",
            remediation=exc.remediation,
            status_code=503,
        )

    @app.exception_handler(GenerationError)
    async def _generation(_request: Request, exc: GenerationError) -> JSONResponse:
        return error_envelope(
            message=str(exc),
            error_type="invalid_request_error",
            remediation=exc.remediation,
            status_code=400,
        )

    @app.exception_handler(CapabilityError)
    async def _capability(_request: Request, exc: CapabilityError) -> JSONResponse:
        return error_envelope(
            message=str(exc),
            error_type="invalid_request_error",
            remediation=exc.remediation,
            status_code=400,
        )

    @app.exception_handler(AISDKError)
    async def _sdk(_request: Request, exc: AISDKError) -> JSONResponse:
        return error_envelope(
            message=str(exc),
            error_type="api_error",
            remediation=exc.remediation,
            status_code=500,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        status = exc.status_code
        error_type = "not_found_error" if status == 404 else "http_error"
        detail = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        return error_envelope(
            message=detail,
            error_type=error_type,
            remediation=GENERIC_REMEDIATION,
            status_code=status,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exception(_request: Request, exc: RequestValidationError) -> JSONResponse:
        del exc
        return error_envelope(
            message="The request body is invalid.",
            error_type="invalid_request_error",
            remediation="Send a JSON body that matches the /v1/chat/completions contract.",
            status_code=400,
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception(_request: Request, exc: Exception) -> JSONResponse:
        del exc
        return error_envelope(
            message="The server failed to handle the request.",
            error_type="internal_error",
            remediation=GENERIC_REMEDIATION,
            status_code=500,
        )
