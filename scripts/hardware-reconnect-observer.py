#!/usr/bin/env python3
"""Observe a Bridge outage and device reconnect without controlling either endpoint."""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import urlsplit

import httpx
from stackchan_bridge.observability.reconnect import (
    ReconnectObservationError,
    observe_reconnect,
)

_DEVICE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def _loopback_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise argparse.ArgumentTypeError("Control API URL must use loopback HTTP")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise argparse.ArgumentTypeError("Control API URL cannot contain credentials or query data")
    return value.rstrip("/")


def _device_id(value: str) -> str:
    if _DEVICE_ID.fullmatch(value) is None:
        raise argparse.ArgumentTypeError("device ID must use 1..64 safe identifier characters")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(prog="hardware-reconnect-observer.py")
    parser.add_argument("--control-url", type=_loopback_url, default="http://127.0.0.1:8766")
    parser.add_argument("--device-id", type=_device_id, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=90)
    parser.add_argument("--poll-interval-seconds", type=float, default=0.1)
    parser.add_argument("--request-timeout-seconds", type=float, default=0.5)
    parser.add_argument("--loss-confirmations", type=int, default=2)
    args = parser.parse_args()

    if not 1 <= args.timeout_seconds <= 300:
        parser.error("--timeout-seconds must be within 1..300")
    if not 0.05 <= args.poll_interval_seconds <= 5:
        parser.error("--poll-interval-seconds must be within 0.05..5")
    if not 0.05 <= args.request_timeout_seconds <= 5:
        parser.error("--request-timeout-seconds must be within 0.05..5")
    if not 1 <= args.loss_confirmations <= 10:
        parser.error("--loss-confirmations must be within 1..10")

    path = f"/v1/control/devices/{args.device_id}"
    try:
        with httpx.Client(
            base_url=args.control_url,
            timeout=args.request_timeout_seconds,
            trust_env=False,
        ) as client:

            def probe() -> bool:
                try:
                    response = client.get(path)
                except httpx.HTTPError:
                    return False
                if response.status_code != 200:
                    return False
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("invalid device response")
                capabilities = payload.get("capabilities")
                if (
                    payload.get("device_id") != args.device_id
                    or payload.get("hardware_model") != "M5STACK-K151"
                    or not isinstance(capabilities, dict)
                    or capabilities.get("head") is not False
                ):
                    raise ValueError("unexpected device identity or motion-lock state")
                return payload.get("connected") is True

            if not probe():
                raise ReconnectObservationError("device must initially be connected")
            print(
                "Initial locked K151 is connected; stop and restart Bridge now. "
                "The observer sends loopback GET requests only.",
                file=sys.stderr,
            )
            observation = observe_reconnect(
                probe,
                timeout_seconds=args.timeout_seconds,
                poll_interval_seconds=args.poll_interval_seconds,
                loss_confirmations=args.loss_confirmations,
            )
    except (httpx.HTTPError, ReconnectObservationError, ValueError):
        print(
            "Reconnect observation failed without exposing the remote response body.",
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            {
                "device_id": args.device_id,
                "display_confirmation": "required",
                "firmware_reboot": "not_determined",
                "loss_confirmations": observation.loss_confirmations,
                "reconnect_ms": round(observation.reconnect_seconds * 1_000, 1),
                "transport_observed": True,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
