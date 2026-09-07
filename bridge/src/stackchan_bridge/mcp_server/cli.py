"""Standalone stdio entry point for StackChan MCP tools."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from ipaddress import ip_address
from os import environ as process_environment
from typing import NoReturn
from urllib.parse import urlsplit

from stackchan_bridge.mcp_server.control_client import ControlApiClient
from stackchan_bridge.mcp_server.server import create_mcp_server

Runner = Callable[[str], int]


def _loopback_control_url(value: str) -> str:
    parsed = urlsplit(value)
    hostname = parsed.hostname
    unsafe_shape = (
        parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or bool(parsed.query)
        or bool(parsed.fragment)
    )
    if parsed.scheme not in {"http", "https"} or hostname is None or unsafe_shape:
        raise argparse.ArgumentTypeError("control URL must use HTTP on loopback")
    try:
        is_loopback = ip_address(hostname).is_loopback
    except ValueError:
        is_loopback = hostname == "localhost"
    if not is_loopback:
        raise argparse.ArgumentTypeError("control URL must use HTTP on loopback")
    return value


def _parser(default_control_url: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stackchan-mcp")
    parser.add_argument(
        "--control-url",
        default=default_control_url,
        type=_loopback_control_url,
        help="loopback StackChan Control API URL",
    )
    return parser


def _run(control_url: str) -> int:
    server = create_mcp_server(ControlApiClient(control_url))
    server.run("stdio")
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    environment: Mapping[str, str] = process_environment,
    runner: Runner = _run,
) -> int:
    """Run the MCP server without writing protocol-unrelated data to stdout."""

    default_control_url = environment.get(
        "STACKCHAN_CONTROL_URL",
        "http://127.0.0.1:8766",
    )
    args = _parser(default_control_url).parse_args(argv)
    return runner(args.control_url)


def entrypoint() -> NoReturn:
    """Console-script adapter."""

    raise SystemExit(main())
