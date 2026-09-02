"""Command-line interface for the CEIA AI SDK.

Typer and Rich stay in this module so ``import ceia_aisdk`` remains
lightweight. Diagnostic collection lives in private modules and is imported
only when ``doctor`` runs.
"""

from __future__ import annotations

import errno
import logging
import socket
import sys
from collections.abc import Callable
from typing import Any

import typer

from ceia_aisdk._model_cli import model_app
from ceia_aisdk.errors import AISDKError, ConfigError, DeviceError, ServerError

_SERVER_EXTRA_REMEDIATION = (
    'Install the extra with pip install "ceia-aisdk[server]" and retry ceia-aisdk serve.'
)
_BIND_REMEDIATION = (
    "Pass --port with a free TCP port, or stop the occupant that is already "
    "listening (for example another local server such as Ollama on 11434)."
)

app = typer.Typer(
    name="ceia-aisdk",
    help=(
        "CEIA AI SDK command-line interface for the local Linux x86_64 "
        "foundation. Use it to inspect whether the package is usable without "
        "downloading models or transmitting data."
    ),
    epilog=(
        "Examples:\n\n  ceia-aisdk doctor\n  ceia-aisdk doctor --help\n"
        "  ceia-aisdk model --help\n  ceia-aisdk serve --help"
    ),
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
    pretty_exceptions_show_locals=False,
)
app.add_typer(model_app, name="model")


@app.callback()
def main() -> None:
    """CEIA AI SDK command-line interface for the local Linux x86_64 foundation.

    Use it to inspect whether the package is usable without downloading models
    or transmitting data. Discover model cache commands with
    ``ceia-aisdk model --help``. Discover the OpenAI-compatible server with
    ``ceia-aisdk serve --help``.
    """
    return


@app.command()
def doctor() -> None:
    """Inspect local machine readiness without downloading or transmitting data.

    The diagnostic supports Linux x86_64. It reports whether a GPU is visible
    and, separately, whether the CUDA inference binding is present. Forcing
    CUDA through configuration can make the command fail when no usable NVIDIA
    GPU is available.

    Examples:
        ceia-aisdk doctor
        CEIA_AISDK_DEVICE=cpu ceia-aisdk doctor
    """
    from ceia_aisdk._diagnostics import build_report, render_report
    from ceia_aisdk._logging import configure_namespace
    from ceia_aisdk.config import AISDKConfig
    from ceia_aisdk.hardware import HardwareSnapshot, ProbeStatus, probe_gpus, select_device

    config = None
    config_error: ConfigError | None = None
    try:
        config = AISDKConfig.load()
    except ConfigError as exc:
        config_error = exc
    except AISDKError as exc:
        _exit_with_unexpected(exc)
        return

    if config is not None:
        configure_namespace(config.log_level)
        snapshot = probe_gpus(requested=config.device)
        selection_error: DeviceError | None = None
        effective_device = None
        try:
            effective_device = select_device(config.device, snapshot)
        except DeviceError as exc:
            selection_error = exc
        from ceia_aisdk.llm.devices import cuda_binding_present

        report = build_report(
            config=config,
            snapshot=snapshot,
            effective_device=effective_device,
            selection_error=selection_error,
            cuda_binding=cuda_binding_present(),
        )
    else:
        snapshot = HardwareSnapshot((), (), ProbeStatus.NOT_RUN, None)
        report = build_report(
            config=None,
            snapshot=snapshot,
            config_error=config_error,
        )

    try:
        render_report(report, stdout=sys.stdout, stderr=sys.stderr)
    except AISDKError as exc:
        _exit_with_unexpected(exc)
        return
    raise typer.Exit(report.exit_code)


@app.command()
def serve(
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help=(
            "Bind address. The default 127.0.0.1 stays on loopback. "
            "Passing 0.0.0.0 exposes the process beyond this machine; TLS is "
            "provided by a reverse proxy, not by this command."
        ),
        show_default=True,
    ),
    port: int = typer.Option(
        11434,
        "--port",
        help="TCP port for the OpenAI-compatible /v1 listener.",
        show_default=True,
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        help="Optional shared secret. When set, every /v1 request needs Bearer auth.",
    ),
    cors: bool = typer.Option(
        False,
        "--cors",
        help="Allow any browser origin. Default CORS allows only localhost origins.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable DEBUG logs. Message bodies are logged only with this flag.",
    ),
) -> None:
    r"""Start a local OpenAI-compatible server on Linux x86_64.

    Requires the server extra: pip install "ceia-aisdk\[server]".
    Clients use the /v1 base URL and opaque aliases such as llm/small.
    Tools use POST /v1/chat/completions; the client executes tool handlers.

    Args:
        host: Bind address. Default 127.0.0.1 stays on loopback.
        port: TCP port. Default 11434.
        token: Optional Bearer secret. Empty values are rejected.
        cors: When true, allow any browser origin.
        debug: When true, enable DEBUG logs; message bodies may be logged.

    Examples:
        ceia-aisdk serve --help
        ceia-aisdk serve
    """
    try:
        run_server(
            host=host,
            port=port,
            token=token,
            cors_open=cors,
            debug=debug,
        )
    except ServerError as exc:
        _exit_with_unexpected(exc)


def run_server(
    *,
    host: str,
    port: int,
    token: str | None,
    cors_open: bool,
    debug: bool,
) -> None:
    """Bind uvicorn to ``host``:``port`` and block until shutdown.

    Args:
        host: Bind address. The documented default is ``127.0.0.1``.
        port: TCP port. The documented default is ``11434``.
        token: Optional Bearer secret. Empty values after stripping are rejected.
        cors_open: When true, allow any browser origin.
        debug: When true, set DEBUG logs and allow message-body logging.

    Raises:
        ServerError: If the ``[server]`` extra is missing, ``token`` is empty,
            or the bind address is already in use.
    """
    secret = _normalize_token(token)
    create_app = _load_create_app()
    asgi_app = create_app(token=secret, cors_open=cors_open, debug=debug)
    try:
        import uvicorn
    except ImportError as exc:
        raise ServerError(
            "The OpenAI-compatible server extra is not installed.",
            remediation=_SERVER_EXTRA_REMEDIATION,
        ) from exc
    _configure_serve_logging(debug=debug)
    _probe_bind(host, port)
    ready_url = f"http://{host}:{port}/v1"
    config = uvicorn.Config(
        asgi_app,
        host=host,
        port=port,
        log_level="debug" if debug else "warning",
        access_log=debug,
    )
    server = uvicorn.Server(config)
    _install_ready_log(server, ready_url)
    try:
        server.run()
    except SystemExit as exc:
        if not getattr(server, "started", False):
            raise ServerError(
                f"Could not bind the OpenAI-compatible server on {host}:{port}.",
                remediation=_BIND_REMEDIATION,
            ) from exc
        raise
    except OSError as exc:
        _raise_bind_failure(host, port, exc)


def _load_create_app() -> Callable[..., Any]:
    """Import ``create_app`` only when ``serve`` is executed.

    Returns:
        The FastAPI application factory.

    Raises:
        ServerError: If FastAPI or the server package cannot be imported.
    """
    try:
        from ceia_aisdk.server.app import create_app
    except ServerError:
        raise
    except ImportError as exc:
        raise ServerError(
            "The OpenAI-compatible server extra is not installed.",
            remediation=_SERVER_EXTRA_REMEDIATION,
        ) from exc
    return create_app


def _normalize_token(token: str | None) -> str | None:
    """Treat a missing token as unset and reject a blank ``--token``.

    Args:
        token: Raw CLI token, if any.

    Returns:
        The stripped secret, or ``None`` when auth is disabled.

    Raises:
        ServerError: If ``token`` is present but empty after stripping.
    """
    if token is None:
        return None
    stripped = token.strip()
    if not stripped:
        raise ServerError(
            "The --token value is empty.",
            remediation="Pass a nonempty --token or omit the flag to disable auth.",
        )
    return stripped


def _configure_serve_logging(*, debug: bool) -> None:
    """Attach a stderr handler so the ready URL is visible.

    Args:
        debug: When true, use DEBUG; otherwise INFO for the ready line.
    """
    from ceia_aisdk._logging import configure_namespace, get_logger

    configure_namespace("DEBUG" if debug else "INFO")
    logger = get_logger("ceia_aisdk.server")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)


def _install_ready_log(server: Any, ready_url: str) -> None:
    """Log the absolute ``/v1`` URL after uvicorn reports it has started.

    Args:
        server: uvicorn ``Server`` instance.
        ready_url: Absolute URL including host, port, and ``/v1``.
    """
    from ceia_aisdk._logging import get_logger

    logger = get_logger("ceia_aisdk.server")
    original_startup = server.startup

    async def startup_with_ready(sockets: object = None) -> None:
        await original_startup(sockets=sockets)
        if getattr(server, "started", False):
            logger.info("OpenAI-compatible server ready at %s", ready_url)

    server.startup = startup_with_ready


def _probe_bind(host: str, port: int) -> None:
    """Fail fast when the bind address is already in use.

    Args:
        host: Bind address to probe.
        port: Bind port to probe.

    Raises:
        ServerError: If the address cannot be bound.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError as exc:
            _raise_bind_failure(host, port, exc)


def _raise_bind_failure(host: str, port: int, exc: OSError) -> None:
    """Map a bind OSError to ``ServerError``.

    Args:
        host: Bind address that failed.
        port: Bind port that failed.
        exc: Operating-system bind error.

    Raises:
        ServerError: Always, with ``--port`` remediation.
    """
    in_use = exc.errno in {errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", errno.EADDRINUSE)}
    message = (
        f"Port {port} on {host} is already in use."
        if in_use
        else f"Could not bind the OpenAI-compatible server on {host}:{port}."
    )
    raise ServerError(message, remediation=_BIND_REMEDIATION) from exc


def _exit_with_unexpected(error: AISDKError) -> None:
    """Print a bounded failure without a native traceback.

    Args:
        error: Public SDK error.
    """
    sys.stderr.write(f"{error}\n{error.remediation}\n")
    raise typer.Exit(code=1)
