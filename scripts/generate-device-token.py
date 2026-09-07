#!/usr/bin/env python3
"""Compatibility wrapper for the one-time Bridge token CLI."""

from __future__ import annotations

import argparse

from stackchan_bridge.cli import main as bridge_main


def main() -> int:
    parser = argparse.ArgumentParser(prog="generate-device-token.py")
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    command = ["token", "create", "--device-id", args.device_id]
    if args.json:
        command.append("--json")
    return bridge_main(command)


if __name__ == "__main__":
    raise SystemExit(main())
