"""Typer sub-application for ``ceia-aisdk model`` commands.

This module is imported only from the CLI entry point so
``import ceia_aisdk`` does not load Typer, Rich, PyYAML, or ``httpx``.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import typer

from ceia_aisdk.config import AISDKConfig
from ceia_aisdk.errors import AISDKError

model_app = typer.Typer(
    name="model",
    help=(
        "Manage opaque cataloged model aliases in the local cache. Aliases such "
        "as llm/small identify a pinned artifact without exposing the upstream "
        "repository or filename."
    ),
    epilog=("Examples:\n\n  ceia-aisdk model --help\n  ceia-aisdk model pull llm/small"),
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
    pretty_exceptions_show_locals=False,
)


@model_app.callback()
def model_group() -> None:
    """Manage opaque cataloged model aliases in the local cache.

    Aliases such as llm/small identify a pinned artifact without exposing the
    upstream repository or filename. Unqualified names such as small are
    treated as llm/small.

    Examples:
        ceia-aisdk model --help
        ceia-aisdk model pull llm/small
    """
    return


@model_app.command("pull")
def pull(
    alias: str | None = typer.Argument(
        default=None,
        help="Cataloged alias such as llm/small, or a documented bypass token.",
    ),
    essentials: bool = typer.Option(
        False,
        "--essentials",
        help="Download every essential alias present in the active catalog.",
    ),
) -> None:
    """Download a cataloged alias into the cache with integrity checking.

    Downloads resume after interruption. A valid cached file is reused and is
    not stored in the package. Progress is shown when stderr is a TTY.

    Args:
        alias: Cataloged alias such as llm/small, or a documented bypass token.
        essentials: When true, download every essential alias in the catalog.

    Examples:
        ceia-aisdk model pull llm/small
        ceia-aisdk model pull --essentials
    """
    if essentials and alias:
        raise typer.BadParameter("ALIAS and --essentials are mutually exclusive.")
    if not essentials and not alias:
        raise typer.BadParameter("Provide ALIAS or --essentials.")
    config = _load_config()
    if essentials:
        _pull_essentials(config)
        return
    assert alias is not None
    _pull_one(alias, config)


@model_app.command("list")
def list_models() -> None:
    """List cached aliases and their sizes.

    An empty cache prints a readable empty-state message and exits 0.

    Examples:
        ceia-aisdk model list
    """
    config = _load_config()
    try:
        from ceia_aisdk.registry.cache import list_cached_artifacts

        items = list_cached_artifacts(config=config)
    except AISDKError as exc:
        exit_with_error(exc)
        return
    if not items:
        typer.echo("No models are cached.")
        return
    for alias, size in items:
        typer.echo(f"{alias}\t{size}")


@model_app.command("rm")
def remove(
    alias: str = typer.Argument(help="Cataloged alias to remove from the cache."),
) -> None:
    """Remove a cached alias, its sidecar, lock, and leftover partial.

    Unrelated files are not deleted.

    Args:
        alias: Cataloged alias to remove from the cache.

    Examples:
        ceia-aisdk model rm llm/small
    """
    config = _load_config()
    try:
        from ceia_aisdk.registry.cache import remove_cached_alias

        remove_cached_alias(alias, config=config, domain=_cli_domain(alias))
    except AISDKError as exc:
        exit_with_error(exc)
        return
    typer.echo(f"Removed {alias}.")


@model_app.command("info")
def info(
    alias: str = typer.Argument(help="Cataloged alias such as llm/small."),
) -> None:
    """Print public metadata for a cataloged alias.

    Catalog authenticity is not verified in this increment. Integrity is the
    artifact SHA-256 checksum, not a catalog signature.

    Args:
        alias: Cataloged alias such as llm/small.

    Examples:
        ceia-aisdk model info llm/small
    """
    config = _load_config()
    try:
        from ceia_aisdk.registry import get_public_metadata, resolve

        resolved = resolve(alias, config=config, domain=_cli_domain(alias))
        meta = get_public_metadata(alias, config=config, domain=_cli_domain(alias))
    except AISDKError as exc:
        exit_with_error(exc)
        return
    lines = [
        f"alias: {resolved.alias}",
        f"license_family: {meta.license_family}",
        f"commercial_use: {meta.commercial_use}",
        f"context_length: {meta.context_length}",
        f"size_gb: {meta.size_gb}",
        f"capabilities: {', '.join(meta.capabilities)}",
        f"quantization_class: {meta.quantization_class}",
    ]
    typer.echo("\n".join(lines))


@model_app.command("verify")
def verify() -> None:
    """Rehash cached cataloged artifacts against the active catalog.

    An empty cache exits 0. A checksum mismatch exits 1 and does not promote
    corrupt files.

    Examples:
        ceia-aisdk model verify
    """
    config = _load_config()
    try:
        from ceia_aisdk.registry.cache import verify_cached_artifacts

        mismatches = verify_cached_artifacts(config=config)
    except AISDKError as exc:
        exit_with_error(exc)
        return
    if not mismatches:
        typer.echo("All cached cataloged artifacts match their checksums.")
        return
    sys.stderr.write("Checksum mismatch in the model cache.\n")
    for path in mismatches:
        sys.stderr.write(f"{path}\n")
    raise typer.Exit(code=1)


@model_app.command("where")
def where(
    alias: str = typer.Argument(help="Cataloged alias such as llm/small."),
) -> None:
    """Print the absolute cache path of a cached alias.

    Args:
        alias: Cataloged alias such as llm/small.

    Examples:
        ceia-aisdk model where llm/small
    """
    config = _load_config()
    try:
        from ceia_aisdk.registry.cache import cached_path

        path = cached_path(alias, config=config, domain=_cli_domain(alias))
    except AISDKError as exc:
        exit_with_error(exc)
        return
    typer.echo(str(path))


def _pull_one(alias: str, config: AISDKConfig) -> None:
    """Download one alias and print the cache path.

    Args:
        alias: Cataloged alias or bypass token.
        config: Effective configuration.
    """
    progress, stop = _tty_progress()
    try:
        from ceia_aisdk.registry import ensure_local

        path = ensure_local(
            alias,
            config=config,
            domain=_cli_domain(alias),
            progress=progress,
        )
    except AISDKError as exc:
        stop()
        exit_with_error(exc)
        return
    stop()
    if not sys.stderr.isatty():
        sys.stderr.write("Download complete.\n")
    typer.echo(str(path))


def _pull_essentials(config: AISDKConfig) -> None:
    """Download essential aliases from the active catalog.

    Args:
        config: Effective configuration.
    """
    from ceia_aisdk.errors import ModelNotFoundError
    from ceia_aisdk.registry.catalog import load_catalog

    catalog = load_catalog(config=config)
    for name in catalog.essentials:
        try:
            from ceia_aisdk.registry.catalog import parse_catalog_alias

            parse_catalog_alias(name)
        except ModelNotFoundError:
            sys.stderr.write(f"Warning: essential alias {name} is missing from the catalog.\n")
            continue
        try:
            catalog.pin(*name.split("/", 1))
        except (KeyError, ValueError):
            sys.stderr.write(f"Warning: essential alias {name} is missing from the catalog.\n")
            continue
        _pull_one(name, config)


def _load_config() -> AISDKConfig:
    """Load process configuration or exit with remediation.

    Returns:
        The effective configuration snapshot.
    """
    try:
        return AISDKConfig.load()
    except AISDKError as exc:
        exit_with_error(exc)
        raise


def _cli_domain(alias: str) -> str | None:
    """Return the CLI default domain for an unqualified catalog alias.

    Args:
        alias: Raw CLI token.

    Returns:
        ``llm`` for unqualified size names, otherwise ``None``.
    """
    if alias.startswith(("hf://", "/", ".", "~")):
        return None
    if Path(alias).expanduser().exists():
        return None
    size_token = alias.split("@", 1)[0]
    if "/" not in size_token:
        return "llm"
    return None


def _tty_progress() -> tuple[Callable[[int, int | None], None] | None, Callable[[], None]]:
    """Return a Rich progress callback when stderr is a TTY.

    Returns:
        A ``(callback, stop)`` pair. ``callback`` is ``None`` when stderr is
        not a TTY.
    """
    if not sys.stderr.isatty():
        return None, lambda: None
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        TextColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )

    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=Console(file=sys.stderr),
        transient=True,
    )
    progress.start()
    task_id = progress.add_task("Downloading", total=None)

    def _update(have: int, total: int | None) -> None:
        progress.update(task_id, completed=have, total=total)

    def _stop() -> None:
        progress.stop()

    return _update, _stop


def exit_with_error(error: AISDKError) -> None:
    """Print a bounded failure without a native traceback.

    Args:
        error: Public SDK error.

    Raises:
        typer.Exit: Always exits with code 1.
    """
    sys.stderr.write(f"{error}\n{error.remediation}\n")
    raise typer.Exit(code=1)
