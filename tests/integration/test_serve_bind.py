"""Integration tests for ``ceia-aisdk serve`` bind defaults and conflicts."""

from __future__ import annotations

import asyncio
import inspect
import logging
import socket
from pathlib import Path

import pytest
import uvicorn

from ceia_aisdk import cli as cli_mod
from ceia_aisdk.errors import ServerError

pytestmark = pytest.mark.enable_socket


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _occupy_loopback_port() -> tuple[socket.socket, int]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    return sock, int(sock.getsockname()[1])


@pytest.fixture
def serve_home(isolated_home: Path) -> Path:
    return isolated_home


def test_serve_option_defaults_are_loopback_11434() -> None:
    signature = inspect.signature(cli_mod.serve)
    host_default = signature.parameters["host"].default
    port_default = signature.parameters["port"].default
    host_value = getattr(host_default, "default", host_default)
    port_value = getattr(port_default, "default", port_default)
    assert host_value == "127.0.0.1"
    assert port_value == 11434
    assert host_value != "0.0.0.0"


def test_serve_override_logs_absolute_v1_url(
    serve_home: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del serve_home

    def _run_until_ready(self: uvicorn.Server, sockets: object = None) -> None:
        wrapped = self.startup

        async def _startup_then_stop(sockets: object = None) -> None:
            await wrapped(sockets=sockets)
            self.should_exit = True

        self.startup = _startup_then_stop
        asyncio.run(self._serve(sockets=sockets))

    monkeypatch.setattr(uvicorn.Server, "run", _run_until_ready)
    port = _free_loopback_port()
    with caplog.at_level(logging.INFO, logger="ceia_aisdk"):
        cli_mod.run_server(
            host="127.0.0.1",
            port=port,
            token=None,
            cors_open=False,
            debug=False,
        )
    assert f"http://127.0.0.1:{port}/v1" in caplog.text


def test_occupied_port_raises_server_error_with_port_remediation() -> None:
    occupant, port = _occupy_loopback_port()
    try:
        with pytest.raises(ServerError) as exc_info:
            cli_mod.run_server(
                host="127.0.0.1",
                port=port,
                token=None,
                cors_open=False,
                debug=False,
            )
        text = f"{exc_info.value} {exc_info.value.remediation}"
        assert "--port" in text
        assert "stop" in text.lower() or "occupant" in text.lower() or "another" in text.lower()
        assert "Traceback" not in text
    finally:
        occupant.close()


def test_empty_token_is_rejected_or_treated_as_unset() -> None:
    with pytest.raises(ServerError) as exc_info:
        cli_mod.run_server(
            host="127.0.0.1",
            port=11434,
            token="   ",
            cors_open=False,
            debug=False,
        )
    assert "token" in str(exc_info.value).lower()
