"""Command-line interface for the CEIA AI SDK.

Typer and Rich stay in this module so ``import ceia_aisdk`` remains
lightweight. Diagnostic collection lives in private modules and is imported
only when ``doctor`` runs.
"""

from __future__ import annotations

import sys

import typer

from ceia_aisdk.errors import AISDKError, ConfigError, DeviceError

app = typer.Typer(
    name="ceia-aisdk",
    help=(
        "CEIA AI SDK command-line interface for the local Linux x86_64 "
        "foundation. Use it to inspect whether the package is usable without "
        "downloading models or transmitting data."
    ),
    epilog="Examples:\n\n  ceia-aisdk doctor\n  ceia-aisdk doctor --help",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
    pretty_exceptions_show_locals=False,
)


@app.callback()
def main() -> None:
    """CEIA AI SDK command-line interface for the local Linux x86_64 foundation.

    Use it to inspect whether the package is usable without downloading models
    or transmitting data.
    """
    return


@app.command()
def doctor() -> None:
    """Inspect local machine readiness without downloading or transmitting data.

    The diagnostic supports Linux x86_64. Forcing CUDA through configuration
    can make the command fail when no usable NVIDIA GPU is available.

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
        report = build_report(
            config=config,
            snapshot=snapshot,
            effective_device=effective_device,
            selection_error=selection_error,
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


def _exit_with_unexpected(error: AISDKError) -> None:
    """Print a bounded failure without a native traceback.

    Args:
        error: Public SDK error.
    """
    sys.stderr.write(f"{error}\n{error.remediation}\n")
    raise typer.Exit(code=1)
