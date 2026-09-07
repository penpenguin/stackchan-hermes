from __future__ import annotations

import socket
from asyncio import create_task, sleep
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI
from stackchan_bridge.captures.coordinator import CaptureCoordinator
from stackchan_bridge.captures.store import CaptureStore
from stackchan_bridge.device_gateway.application import (
    DeviceGatewayConfig,
    create_device_gateway_app,
)
from stackchan_bridge.security.tokens import hash_device_token
from stackchan_simulator.device import DeviceSimulator, SimulatorConfig
from uvicorn import Config, Server


@asynccontextmanager
async def live_gateway(
    capture_store: CaptureStore | None = None,
) -> AsyncIterator[tuple[str, FastAPI]]:
    token = "simulator-device-token"  # pragma: allowlist secret
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        capture_store=capture_store,
    )
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = Server(
        Config(
            app,
            log_level="critical",
            access_log=False,
            lifespan="off",
        )
    )
    server_task = create_task(server.serve(sockets=[listener]))
    for _ in range(100):
        if server.started:
            break
        await sleep(0.01)
    else:
        server.should_exit = True
        await server_task
        raise RuntimeError("test gateway did not start")

    try:
        yield f"ws://127.0.0.1:{port}/v1/device/ws", app
    finally:
        server.should_exit = True
        await server_task


@pytest.mark.asyncio
async def test_device_simulator_handshakes_with_the_real_bridge_gateway() -> None:
    async with live_gateway() as (bridge_url, app):
        simulator = DeviceSimulator(
            SimulatorConfig(
                bridge_url=bridge_url,
                device_id="sim-001",
                token="simulator-device-token",  # pragma: allowlist secret
            )
        )

        acknowledgement = await simulator.handshake()

    assert acknowledgement.payload.selected_protocol_version == 1
    assert app.state.device_registry.connected_device_ids() == ()


@pytest.mark.asyncio
async def test_real_bridge_and_simulator_complete_a_command_round_trip() -> None:
    async with live_gateway() as (bridge_url, app):
        simulator = DeviceSimulator(
            SimulatorConfig(
                bridge_url=bridge_url,
                device_id="sim-001",
                token="simulator-device-token",  # pragma: allowlist secret
            )
        )
        simulator_task = create_task(simulator.run_one_command())
        for _ in range(100):
            if app.state.device_registry.connected_device_ids() == ("sim-001",):
                break
            await sleep(0.01)
        else:
            raise RuntimeError("Simulator did not register")

        result = await app.state.device_registry.send_command(
            "sim-001",
            "head.set_angles",
            {"yaw": 15, "pitch": 40, "speed": 30},
        )
        received_command = await simulator_task

    assert result.payload.ok is True
    assert result.payload.result == {"yaw": 15, "pitch": 40}
    assert result.request_id == received_command.request_id
    assert simulator.head_angles == (15, 40)


@pytest.mark.asyncio
async def test_real_gateway_and_simulator_complete_authenticated_capture_upload(
    tmp_path: Path,
) -> None:
    store = CaptureStore(
        directory=tmp_path,
        ttl_seconds=600,
        max_bytes=2_097_152,
    )
    async with live_gateway(store) as (bridge_url, app):
        simulator = DeviceSimulator(
            SimulatorConfig(
                bridge_url=bridge_url,
                device_id="sim-001",
                token="simulator-device-token",  # pragma: allowlist secret
            )
        )
        simulator_task = create_task(simulator.run_capture_command())
        for _ in range(100):
            if app.state.device_registry.connected_device_ids() == ("sim-001",):
                break
            await sleep(0.01)
        else:
            raise RuntimeError("Simulator did not register")
        coordinator = CaptureCoordinator(
            app.state.device_registry,
            store,
            timeout_seconds=2,
        )

        record = await coordinator.take_photo("sim-001", quality=75)
        received_command = await simulator_task

    assert received_command.payload.name == "camera.capture"
    assert received_command.payload.args.capture_id == record.capture_id
    assert (record.width, record.height) == (320, 240)
    assert record.path.is_file()
