#!/usr/bin/env python3
"""Conservative Control API smoke check; physical motion requires explicit safeguards."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from stackchan_bridge.doctor import firmware_backup_is_verified


def _loopback_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise argparse.ArgumentTypeError("Control API URL must use loopback HTTP")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise argparse.ArgumentTypeError("Control API URL cannot contain credentials or query data")
    return value.rstrip("/")


def main() -> int:
    parser = argparse.ArgumentParser(prog="hardware-smoke-test.py")
    parser.add_argument("--control-url", type=_loopback_url, default="http://127.0.0.1:8766")
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--backup-directory", type=Path, default=Path("firmware/backups"))
    parser.add_argument("--allow-motion", action="store_true")
    parser.add_argument("--yaw", type=float)
    parser.add_argument("--pitch", type=float)
    parser.add_argument("--home", action="store_true")
    parser.add_argument("--safe-visual", action="store_true")
    parser.add_argument("--restore-brightness", type=int)
    parser.add_argument("--hold-seconds", type=float, default=10)
    args = parser.parse_args()
    if args.home and not args.allow_motion:
        parser.error("--home requires --allow-motion")
    if args.home and (args.yaw is not None or args.pitch is not None):
        parser.error("--home cannot be combined with --yaw or --pitch")

    try:
        with httpx.Client(base_url=args.control_url, timeout=5, trust_env=False) as client:
            status = client.get(f"/v1/control/devices/{args.device_id}")
            status.raise_for_status()
            payload = status.json()
            if not isinstance(payload, dict):
                raise ValueError("invalid status response")
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

            if args.safe_visual:
                if args.allow_motion:
                    parser.error("--safe-visual cannot be combined with --allow-motion")
                if args.restore_brightness is None:
                    parser.error("--safe-visual requires --restore-brightness")
                if not 0 <= args.restore_brightness <= 100:
                    parser.error("--restore-brightness must be within 0..100")
                if not 0 <= args.hold_seconds <= 60:
                    parser.error("--hold-seconds must be within 0..60")
                capabilities = payload.get("capabilities")
                if payload.get("hardware_model") != "M5STACK-K151" or not isinstance(
                    capabilities, dict
                ):
                    parser.error("safe visual check requires a connected M5STACK-K151")
                if capabilities.get("head") is not False:
                    parser.error("safe visual check requires the physical head lock")
                if (
                    capabilities.get("avatar") is not True
                    or capabilities.get("display") is not True
                    or not isinstance(capabilities.get("led_count"), int)
                    or capabilities["led_count"] < 1
                ):
                    parser.error("safe visual check requires avatar, display and LED capabilities")

                command_url = f"/v1/control/devices/{args.device_id}/commands"

                def send(name: str, command_args: dict[str, object]) -> None:
                    response = client.post(
                        command_url,
                        json={"name": name, "args": command_args},
                    )
                    response.raise_for_status()
                    command_result = response.json()
                    if not isinstance(command_result, dict) or command_result.get("ok") is not True:
                        raise ValueError("safe visual command was rejected")

                try:
                    send("avatar.set_expression", {"expression": "happy"})
                    send("led.set_all", {"r": 0, "g": 16, "b": 64})
                    send("display.set_brightness", {"brightness": 35})
                    print("Safe visual state applied; no head command was sent.")
                    time.sleep(args.hold_seconds)
                finally:
                    restore_failed = False
                    restore_commands = (
                        (
                            "display.set_brightness",
                            {"brightness": args.restore_brightness},
                        ),
                        ("led.clear", {}),
                        ("avatar.set_expression", {"expression": "idle"}),
                    )
                    for name, command_args in restore_commands:
                        try:
                            send(name, command_args)
                        except (httpx.HTTPError, ValueError):
                            restore_failed = True
                    if restore_failed:
                        raise httpx.HTTPError("safe visual restoration failed")
                    print("Safe visual state restored; no head command was sent.")
                return 0

            if not args.allow_motion:
                print("Read-only status smoke test completed; no physical command was sent.")
                return 0
            if payload.get("hardware_model") != "M5STACK-K151":
                parser.error("motion requires a connected, confirmed M5STACK-K151")
            capabilities = payload.get("capabilities")
            if not isinstance(capabilities, dict) or capabilities.get("head") is not True:
                parser.error("motion requires an explicitly unlocked head capability")
            if not firmware_backup_is_verified(args.backup_directory):
                parser.error("motion requires a verified factory backup")
            if args.home:
                command_name = "head.home"
                command_args: dict[str, object] = {}
            else:
                if args.yaw is None or args.pitch is None:
                    parser.error("--allow-motion requires explicit --yaw and --pitch")
                if not -10 <= args.yaw <= 10 or not 35 <= args.pitch <= 45:
                    parser.error(
                        "initial smoke motion must stay within yaw -10..10 and pitch 35..45"
                    )
                command_name = "head.set_angles"
                command_args = {"yaw": args.yaw, "pitch": args.pitch, "speed": 10}
            motion = client.post(
                f"/v1/control/devices/{args.device_id}/commands",
                json={"name": command_name, "args": command_args},
            )
            motion.raise_for_status()
            motion_payload = motion.json()
            if not isinstance(motion_payload, dict) or motion_payload.get("ok") is not True:
                raise ValueError("motion command was rejected")
            print(json.dumps(motion_payload, ensure_ascii=False, indent=2, sort_keys=True))
    except (httpx.HTTPError, ValueError):
        print("Hardware smoke test failed without exposing the remote response body.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
