from __future__ import annotations

from pathlib import Path
from typing import cast
from uuid import uuid4

import httpx
import pytest
from fastapi import WebSocket
from stackchan_bridge.captures.coordinator import CaptureCoordinator
from stackchan_bridge.captures.store import CaptureStore
from stackchan_bridge.control.application import create_control_app
from stackchan_bridge.device_gateway.application import DeviceConnection, DeviceRegistry
from stackchan_bridge.hermes.segmenter import SpeechSegmenterConfig
from stackchan_bridge.tts.adapters import MockTtsAdapter
from stackchan_bridge.tts.pipeline import SegmentPlaybackPipeline
from stackchan_bridge.turns.coordinator import TurnCoordinator
from stackchan_bridge.turns.vision import VisionTurnService
from stackchan_simulator.fixtures import generate_synthetic_jpeg

from .test_capture_coordinator import UploadingCaptureWebSocket
from .test_control_api import simulator_hello
from .test_vision_turn import RecordingPlayer, RecordingVisionHermes


@pytest.mark.parametrize("endpoint", ["captures", "vision"])
async def test_capture_capacity_returns_429_and_recovers_after_retention(
    tmp_path: Path, endpoint: str
) -> None:
    wall = [0.0]
    store = CaptureStore(
        directory=tmp_path,
        ttl_seconds=600,
        max_bytes=2_097_152,
        clock=lambda: wall[0],
        monotonic_clock=lambda: 0.0,
    )
    for _ in range(1024):
        store.reserve("sim-001")
    registry = DeviceRegistry(command_timeout_seconds=5)
    connection_id = uuid4()
    websocket = UploadingCaptureWebSocket(registry, connection_id, store)
    await registry.register(
        DeviceConnection(
            connection_id=connection_id,
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, websocket),
        )
    )
    captures = CaptureCoordinator(registry, store, timeout_seconds=10)
    hermes = RecordingVisionHermes(generate_synthetic_jpeg())
    player = RecordingPlayer()
    vision = VisionTurnService(
        coordinator=TurnCoordinator(),
        captures=captures,
        hermes=hermes,
        tts_pipeline=SegmentPlaybackPipeline(MockTtsAdapter(), player, timeout_seconds=1),
        segmenter_config=SpeechSegmenterConfig(),
    )
    app = create_control_app(
        registry, capture_store=store, capture_coordinator=captures, vision_turn_service=vision
    )
    url = f"/v1/control/devices/sim-001/{endpoint}"
    body = {"question": "何が見えますか"} if endpoint == "vision" else {}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://control"
    ) as client:
        response = await client.post(url, json=body)
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "CAPTURE_CAPACITY"
        assert response.json()["error"]["details"] == {"reason": "CAPTURE_CAPACITY"}
        assert websocket.command is None
        assert hermes.calls == []
        assert player.played == []

        wall[0] = 601
        response = await client.post(url, json=body)
        assert response.status_code == (201 if endpoint == "captures" else 200)
        assert websocket.command is not None
