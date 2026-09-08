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
from stackchan_bridge.protocol.models import CommandMessage, CommandResultMessage
from stackchan_bridge.tts.adapters import MockTtsAdapter
from stackchan_bridge.tts.pipeline import SegmentPlaybackPipeline
from stackchan_bridge.turns.coordinator import TurnCoordinator
from stackchan_bridge.turns.vision import VisionTurnService
from stackchan_simulator.fixtures import generate_synthetic_jpeg

from .test_control_api import simulator_hello
from .test_vision_turn import RecordingPlayer, RecordingVisionHermes


@pytest.mark.parametrize("endpoint", ["captures", "vision"])
@pytest.mark.parametrize("purge", [False, True])
async def test_expired_capture_diagnostics_return_a_control_error_and_release_busy(
    tmp_path: Path, endpoint: str, purge: bool
) -> None:
    wall = [0.0]
    store = CaptureStore(
        directory=tmp_path, ttl_seconds=1, max_bytes=2_097_152, clock=lambda: wall[0]
    )
    registry = DeviceRegistry(command_timeout_seconds=5)
    connection_id = uuid4()
    capture_ids: list[str] = []

    class ExpiringUpload:
        async def send_text(self, data: str) -> None:
            command = CommandMessage.model_validate_json(data)
            if command.payload.name != "camera.capture":
                return
            capture_id = command.payload.args.capture_id
            capture_ids.append(str(capture_id))
            store.save(
                capture_id,
                device_id="sim-001",
                content_type="image/jpeg",
                body=generate_synthetic_jpeg(),
            )
            # Storage succeeds, but retention ends before Firmware completion arrives.
            wall[0] += 2
            if purge:
                store.purge_expired()
            registry.route_result(
                "sim-001",
                connection_id,
                CommandResultMessage.model_validate(
                    {
                        "v": 1,
                        "type": "command_result",
                        "message_id": str(uuid4()),
                        "request_id": command.request_id,
                        "sent_at_ms": 1,
                        "payload": {"ok": True, "result": {}},
                    }
                ),
            )

    await registry.register(
        DeviceConnection(
            connection_id=connection_id,
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, ExpiringUpload()),
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
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://control",
    ) as client:
        for _ in range(2):
            response = await client.post(
                f"/v1/control/devices/sim-001/{endpoint}",
                json={"question": "何が見えますか"} if endpoint == "vision" else {},
            )
            assert response.status_code == (409 if purge else 504)
            error = response.json()["error"]
            assert error["code"] == ("CAPTURE_FAILED" if purge else "CAPTURE_EXPIRED")
            assert error["details"]["reason"] == (
                "CAPTURE_NOT_FOUND" if purge else "CAPTURE_EXPIRED"
            )
            assert error["details"]["capture_id"] == capture_ids[-1]
            assert error["details"]["stage"] == "unavailable"
            assert error["details"]["image_saved"] is None
    assert len(set(capture_ids)) == 2
    assert hermes.calls == []
    assert player.played == []
