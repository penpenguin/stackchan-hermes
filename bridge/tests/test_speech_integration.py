from __future__ import annotations

import json
from asyncio import CancelledError, Event, sleep, wait_for
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import WebSocket
from mcp.server.mcpserver.exceptions import ToolError
from prometheus_client import generate_latest
from stackchan_bridge.audio.codec import OpusCodec, OpusCodecConfig
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.audio.wav import pcm_to_wav
from stackchan_bridge.config import load_settings
from stackchan_bridge.device_gateway.application import DeviceConnection
from stackchan_bridge.mcp_server.control_client import ControlApiClient
from stackchan_bridge.mcp_server.server import create_mcp_server
from stackchan_bridge.protocol.models import (
    AudioOutputEndMessage,
    AudioOutputStartMessage,
    parse_text_frame,
)
from stackchan_bridge.runtime import build_runtime

from .test_control_api import simulator_hello

ROOT = Path(__file__).resolve().parents[2]


class IdleSpeechDevice:
    """Receive downstream audio without ever sending a microphone stream."""

    def __init__(self) -> None:
        self.starts: list[AudioOutputStartMessage] = []
        self.ends: list[AudioOutputEndMessage] = []
        self.pcm: list[bytes] = []
        self.decoder = OpusCodec(OpusCodecConfig(frame_ms=60))

    async def send_text(self, data: str) -> None:
        message = parse_text_frame(data)
        if isinstance(message, AudioOutputStartMessage):
            self.starts.append(message)
        else:
            assert isinstance(message, AudioOutputEndMessage)
            self.ends.append(message)

    async def send_bytes(self, data: bytes) -> None:
        self.pcm.append(self.decoder.decode(data))


def speech_settings(tmp_path: Path):
    environment = {
        "STACKCHAN_DEVICE_TOKEN": "test-device-token",  # pragma: allowlist secret
        "HERMES_API_KEY": "test-hermes-key",  # pragma: allowlist secret
    }
    settings = load_settings(
        ROOT / "config.example.toml",
        environment=environment,
        cli_overrides={
            "captures": {"directory": str(tmp_path)},
            "mdns": {"enabled": False},
            "audio": {"tts_preroll_ms": 0, "tts_postroll_ms": 0},
            "stt": {"adapter": "http", "endpoint": "http://127.0.0.1:8089/stt"},
            "tts": {
                "adapter": "openai",
                "endpoint": "http://127.0.0.1:8088/speech",
                "model": "test-model",
                "voice": "test-voice",
                "speed": 1.25,
            },
        },
    )
    return settings, environment


@pytest.mark.asyncio
async def test_mcp_to_runtime_tts_and_idle_device_opus_playback(tmp_path: Path) -> None:
    settings, environment = speech_settings(tmp_path)
    release = Event()
    started = Event()
    texts: list[str] = []
    forbidden_requests = []

    async def forbidden(request: httpx.Request) -> httpx.Response:
        forbidden_requests.append(request)
        return httpx.Response(500)

    async def synthesize(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["voice"] == "test-voice"
        assert payload["speed"] == 1.25
        texts.append(payload["input"])
        started.set()
        await release.wait()
        return httpx.Response(
            200,
            content=pcm_to_wav(PcmAudio(pcm=b"\x00\x10" * 960)),
            headers={"Content-Type": "audio/wav"},
        )

    runtime = build_runtime(
        settings,
        environment=environment,
        hermes_transport=httpx.MockTransport(forbidden),
        stt_transport=httpx.MockTransport(forbidden),
        tts_transport=httpx.MockTransport(synthesize),
    )
    device = IdleSpeechDevice()
    await runtime.registry.register(
        DeviceConnection(
            device_id="sim-001",
            connection_id=uuid4(),
            hello=simulator_hello(),
            websocket=cast(WebSocket, device),
        )
    )
    control = ControlApiClient(
        "http://127.0.0.1:8766", transport=httpx.ASGITransport(app=runtime.control)
    )
    mcp = create_mcp_server(control)
    try:
        text = "あ" * 161 + "最後です。"
        result = await mcp.call_tool("stackchan_speak", {"device_id": "sim-001", "text": text})
        accepted = result.structured_content
        assert accepted["state"] == "ACCEPTED"
        assert device.starts == []
        await wait_for(started.wait(), 1)
        with pytest.raises(ToolError, match="TURN_BUSY"):
            await mcp.call_tool("stackchan_speak", {"device_id": "sim-001", "text": "重複"})
        release.set()

        async def poll():
            while True:
                response = await mcp.call_tool(
                    "stackchan_get_speech_status",
                    {
                        "device_id": "sim-001",
                        "turn_id": accepted["turn_id"],
                    },
                )
                status = response.structured_content
                if status["state"] not in {"ACCEPTED", "RUNNING"}:
                    return status
                await sleep(0.01)

        assert (await wait_for(poll(), 5))["state"] == "COMPLETED"
        assert "".join(texts) == text
        assert len(device.starts) == len(device.ends) == len(texts) == 3
        assert all(start.turn_id == UUID(accepted["turn_id"]) for start in device.starts)
        assert [start.stream_id for start in device.starts] == [
            end.stream_id for end in device.ends
        ]
        assert all(end.payload.reason == "completed" for end in device.ends)
        assert device.pcm and any(b != 0 for pcm in device.pcm for b in pcm)
        assert forbidden_requests == []
        metrics = generate_latest(runtime.metrics.registry)
        assert b"tts_duration_seconds_count 3.0" in metrics
        assert b"time_to_first_audio_seconds_count 1.0" in metrics
        assert b"active_turns 0.0" in metrics
    finally:
        await runtime.aclose()


@pytest.mark.asyncio
async def test_runtime_stops_background_speech_before_closing_provider_clients(
    tmp_path: Path,
) -> None:
    settings, environment = speech_settings(tmp_path)
    started, cancelled = Event(), Event()

    async def synthesize(request: httpx.Request) -> httpx.Response:
        started.set()
        try:
            await Event().wait()
        except CancelledError:
            assert all(not client.is_closed for client in runtime.provider_http_clients)
            cancelled.set()
            raise
        raise AssertionError("unreachable")

    runtime = build_runtime(
        settings, environment=environment, tts_transport=httpx.MockTransport(synthesize)
    )
    await runtime.registry.register(
        DeviceConnection(
            device_id="sim-001",
            connection_id=uuid4(),
            hello=simulator_hello(),
            websocket=cast(WebSocket, IdleSpeechDevice()),
        )
    )
    try:
        accepted = await runtime.speech_turn_service.start("sim-001", text="終了時の停止")
        await wait_for(started.wait(), 1)
    finally:
        await runtime.aclose()
    assert cancelled.is_set()
    assert runtime.speech_turn_service.get("sim-001", accepted.turn_id).state == "CANCELLED"
    assert runtime.turn_coordinator.current("sim-001") is None
    assert all(client.is_closed for client in runtime.provider_http_clients)
