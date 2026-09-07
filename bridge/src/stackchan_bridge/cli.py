"""Command-line entry point for the Bridge."""

from __future__ import annotations

import argparse
import json
import re
import stat
import sys
from collections.abc import Callable, Mapping, Sequence
from ctypes.util import find_library as system_find_library
from os import environ as process_environment
from pathlib import Path
from secrets import token_urlsafe
from shutil import which as system_which
from time import time
from typing import NoReturn

import httpx
from pydantic import TypeAdapter, ValidationError

from stackchan_bridge.config import BridgeSettings, load_settings
from stackchan_bridge.doctor import (
    CheckStatus,
    FindLibrary,
    HostCheck,
    PortChecker,
    Which,
    host_is_ready,
    inspect_host,
    inspect_online,
)
from stackchan_bridge.protocol.models import DeviceId
from stackchan_bridge.runtime import run_servers
from stackchan_bridge.security.tokens import hash_device_token

ServeRunner = Callable[[BridgeSettings, Mapping[str, str]], int]
TokenFactory = Callable[[], str]
DevicesRunner = Callable[[BridgeSettings, bool], int]
CapturesRunner = Callable[[BridgeSettings, str, bool], int]
_DEVICE_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(DeviceId)
_CAPTURE_FILENAME = re.compile(r"^(?P<id>[0-9a-f]{32})\.jpg$")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stackchan-bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="inspect host prerequisites")
    doctor.add_argument(
        "--offline",
        action="store_true",
        help="skip Hermes and other network probes",
    )
    doctor.add_argument("--config", type=Path)
    doctor.add_argument("--json", action="store_true", dest="as_json")

    serve = subparsers.add_parser("serve", help="serve device and loopback APIs")
    serve.add_argument("--config", type=Path)
    serve.add_argument("--device-host")
    serve.add_argument("--device-port", type=int)
    serve.add_argument("--control-host")
    serve.add_argument("--control-port", type=int)

    devices = subparsers.add_parser("devices", help="list connected devices")
    devices.add_argument("--config", type=Path)
    devices.add_argument("--control-host")
    devices.add_argument("--control-port", type=int)
    devices.add_argument("--json", action="store_true", dest="as_json")

    captures = subparsers.add_parser("captures", help="inspect temporary captures")
    capture_commands = captures.add_subparsers(dest="capture_command", required=True)
    for name in ("list", "purge"):
        capture_command = capture_commands.add_parser(name)
        capture_command.add_argument("--config", type=Path)
        capture_command.add_argument("--json", action="store_true", dest="as_json")

    token = subparsers.add_parser("token", help="manage device credentials")
    token_commands = token.add_subparsers(dest="token_command", required=True)
    token_create = token_commands.add_parser("create", help="create a one-time device token")
    token_create.add_argument("--device-id", required=True)
    token_create.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    which: Which = system_which,
    find_library: FindLibrary = system_find_library,
    environment: Mapping[str, str] = process_environment,
    serve_runner: ServeRunner = run_servers,
    devices_runner: DevicesRunner = lambda settings, as_json: list_devices(settings, as_json),
    captures_runner: CapturesRunner = (
        lambda settings, action, as_json: manage_captures(settings, action, as_json)
    ),
    token_factory: TokenFactory = lambda: token_urlsafe(32),
    doctor_transport: httpx.BaseTransport | None = None,
    doctor_port_checker: PortChecker | None = None,
) -> int:
    """Run the CLI and return a process exit code."""

    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "token":
        try:
            device_id = _DEVICE_ID_ADAPTER.validate_python(args.device_id)
        except ValidationError:
            parser.error("invalid device id")
        token = token_factory()
        encoded_hash = hash_device_token(token)
        if args.as_json:
            print(
                json.dumps(
                    {
                        "device_id": device_id,
                        "token": token,
                        "token_hash": encoded_hash,
                    },
                    sort_keys=True,
                )
            )
        else:
            print(f"device_id: {device_id}")
            print(f"token (shown once): {token}")
            print(f"token_hash: {encoded_hash}")
        return 0
    if args.command == "serve":
        overrides: dict[str, object] = {}
        device_overrides = {
            key: value
            for key, value in {"host": args.device_host, "port": args.device_port}.items()
            if value is not None
        }
        control_overrides = {
            key: value
            for key, value in {"host": args.control_host, "port": args.control_port}.items()
            if value is not None
        }
        if device_overrides:
            overrides["device_gateway"] = device_overrides
        if control_overrides:
            overrides["control_api"] = control_overrides
        settings = load_settings(
            args.config,
            environment=environment,
            cli_overrides=overrides,
        )
        return serve_runner(settings, environment)
    if args.command == "devices":
        control_overrides = {
            key: value
            for key, value in {"host": args.control_host, "port": args.control_port}.items()
            if value is not None
        }
        device_cli_overrides = {"control_api": control_overrides} if control_overrides else None
        settings = load_settings(
            args.config,
            environment=environment,
            cli_overrides=device_cli_overrides,
        )
        return devices_runner(settings, args.as_json)
    if args.command == "captures":
        settings = load_settings(args.config, environment=environment)
        return captures_runner(settings, args.capture_command, args.as_json)
    if args.command != "doctor":  # pragma: no cover - guarded by argparse
        parser.error(f"unsupported command: {args.command}")
    checks = inspect_host(which=which, find_library=find_library)
    mode = "offline" if args.offline else "online"
    if not args.offline:
        try:
            settings = load_settings(args.config, environment=environment)
        except (OSError, ValueError):
            checks = (
                *checks,
                HostCheck(
                    name="configuration",
                    status=CheckStatus.MISSING,
                    required=True,
                    detail="configuration could not be loaded",
                ),
            )
        else:
            checks = inspect_online(
                settings,
                environment=environment,
                host_checks=checks,
                transport=doctor_transport,
                port_checker=doctor_port_checker,
            )
    ready = host_is_ready(checks)
    payload = {
        "mode": mode,
        "ready": ready,
        "checks": {check.name: check.as_dict() for check in checks},
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for check in checks:
            requirement = "required" if check.required else "optional"
            detail = f" ({check.detail})" if check.detail else ""
            print(f"{check.name}: {check.status.value} [{requirement}]{detail}")
    return 0 if ready else 1


def list_devices(
    settings: BridgeSettings,
    as_json: bool,
    *,
    transport: httpx.BaseTransport | None = None,
) -> int:
    host = settings.control_api.host
    authority = f"[{host}]" if ":" in host else host
    try:
        with httpx.Client(
            base_url=f"http://{authority}:{settings.control_api.port}",
            timeout=5,
            transport=transport,
            trust_env=False,
        ) as client:
            response = client.get("/v1/control/devices")
            response.raise_for_status()
        if len(response.content) > 1_048_576:
            raise ValueError("device response exceeds limit")
        payload = response.json()
        devices = payload.get("devices") if isinstance(payload, dict) else None
        if not isinstance(devices, list) or not all(isinstance(item, dict) for item in devices):
            raise ValueError("invalid device response")
    except (httpx.HTTPError, ValueError):
        print("StackChan Control API is unavailable or returned invalid data", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps({"devices": devices}, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for device in devices:
            print(
                f"{device.get('device_id', 'unknown')}\t{device.get('firmware_version', 'unknown')}"
            )
    return 0


def manage_captures(
    settings: BridgeSettings,
    action: str,
    as_json: bool,
    *,
    clock: Callable[[], float] = time,
) -> int:
    """List or purge only generated temporary JPEG files."""

    directory = settings.captures.directory.resolve()
    now = clock()
    records: list[dict[str, object]] = []
    if directory.is_dir():
        try:
            entries = sorted(directory.iterdir(), key=lambda path: path.name)
            for entry in entries:
                match = _CAPTURE_FILENAME.fullmatch(entry.name)
                if match is None:
                    continue
                file_stat = entry.lstat()
                if not stat.S_ISREG(file_stat.st_mode):
                    continue
                expires_at = file_stat.st_mtime + settings.captures.ttl_seconds
                expired = expires_at <= now
                if action == "purge" and expired:
                    entry.unlink()
                records.append(
                    {
                        "capture_id": match.group("id"),
                        "filename": entry.name,
                        "size_bytes": file_stat.st_size,
                        "modified_at": file_stat.st_mtime,
                        "expires_at": expires_at,
                        "expired": expired,
                    }
                )
        except OSError:
            print("capture storage is unavailable", file=sys.stderr)
            return 1
    if action not in {"list", "purge"}:  # pragma: no cover - guarded by argparse
        raise ValueError("unsupported capture action")
    payload: dict[str, object]
    if action == "purge":
        purged = sum(1 for record in records if record["expired"] is True)
        payload = {"purged": purged}
    else:
        payload = {"captures": records}
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    elif action == "purge":
        print(f"purged: {payload['purged']}")
    else:
        for record in records:
            status = "expired" if record["expired"] else "active"
            print(f"{record['capture_id']}\t{record['size_bytes']}\t{status}")
    return 0


def entrypoint() -> NoReturn:
    """Console-script adapter."""

    raise SystemExit(main())
