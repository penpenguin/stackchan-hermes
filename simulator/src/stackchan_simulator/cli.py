"""Command-line entry point for the Device Simulator scaffold."""

from __future__ import annotations

import argparse
import os
from asyncio import run
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import NoReturn

from stackchan_simulator import __version__
from stackchan_simulator.device import DeviceSimulator, SimulatorConfig, SimulatorFault

Runner = Callable[[SimulatorConfig], int]


def run_simulator(config: SimulatorConfig) -> int:
    simulator = DeviceSimulator(config)
    if config.fault is not None:
        run(simulator.run_fault(config.fault))
        print(f"fault injected: {config.fault.value}")
        return 0
    if config.input_wav is not None and config.output_wav is not None:
        result = run(simulator.run_voice_turn())
        print(
            f"voice turn completed: input_packets={result.input_packets} "
            f"output_packets={result.output_packets} output_streams={result.output_streams}"
        )
        return 0
    acknowledgement = run(simulator.handshake())
    print(f"connected: {acknowledgement.payload.connection_id}")
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] = os.environ,
    runner: Runner = run_simulator,
) -> int:
    """Run the simulator scaffold CLI and return a process exit code."""

    parser = argparse.ArgumentParser(prog="stackchan-simulator")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--bridge")
    parser.add_argument("--device-id")
    parser.add_argument("--token-env")
    parser.add_argument("--input-wav")
    parser.add_argument("--output-wav")
    parser.add_argument("--protocol-version", action="append", type=int)
    parser.add_argument("--command-delay-ms", type=int, default=0)
    parser.add_argument("--output-segment-grace-ms", type=int, default=30_000)
    parser.add_argument("--fault", choices=tuple(fault.value for fault in SimulatorFault))
    args = parser.parse_args(argv)
    if args.version:
        print(f"stackchan-simulator {__version__}")
        return 0
    if args.bridge is None:
        parser.print_help()
        return 0
    if not args.device_id or not args.token_env:
        parser.error("--bridge requires --device-id and --token-env")
    if bool(args.input_wav) != bool(args.output_wav):
        parser.error("--input-wav and --output-wav must be provided together")
    if not 0 <= args.command_delay_ms <= 30_000:
        parser.error("--command-delay-ms must be between 0 and 30000")
    if not 1 <= args.output_segment_grace_ms <= 300_000:
        parser.error("--output-segment-grace-ms must be between 1 and 300000")
    token = environ.get(args.token_env, "")
    if not token:
        parser.error(f"token environment variable is empty or missing: {args.token_env}")
    config = SimulatorConfig(
        bridge_url=args.bridge,
        device_id=args.device_id,
        token=token,
        input_wav=Path(args.input_wav) if args.input_wav else None,
        output_wav=Path(args.output_wav) if args.output_wav else None,
        protocol_versions=tuple(args.protocol_version or (1,)),
        command_delay_seconds=args.command_delay_ms / 1_000,
        output_segment_grace_seconds=args.output_segment_grace_ms / 1_000,
        fault=SimulatorFault(args.fault) if args.fault else None,
    )
    return runner(config)


def entrypoint() -> NoReturn:
    """Console-script adapter."""

    raise SystemExit(main())
