from __future__ import annotations

import socket
from asyncio import create_task, sleep, wait_for
from pathlib import Path

import httpx
import numpy as np
import pytest
import soundfile  # type: ignore[import-untyped]
from stackchan_bridge.audio.codec import OpusCodec, OpusCodecConfig
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.audio.wav import pcm_to_wav
from stackchan_bridge.config import load_settings
from stackchan_bridge.protocol.models import (
    AudioInputEndMessage,
    AudioInputStartMessage,
    AudioOutputEndMessage,
    AudioOutputStartMessage,
    HelloAckMessage,
    HelloMessage,
    ProtocolMessageError,
    parse_text_frame,
)
from stackchan_bridge.runtime import build_runtime
from stackchan_simulator.device import DeviceSimulator, SimulatorConfig
from stackchan_simulator.mock_hermes import MockHermesConfig, create_mock_hermes_app
from uvicorn import Config, Server
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

ROOT = Path(__file__).resolve().parents[2]


def sine_pcm(frame_ms: int) -> bytes:
    sample_count = 16_000 * frame_ms // 1_000
    times = np.arange(sample_count, dtype=np.float64) / 16_000
    return (np.sin(2 * np.pi * 440 * times) * 12_000).astype("<i2").tobytes()


@pytest.mark.asyncio
async def test_simulator_rejects_input_longer_than_protocol_limit(tmp_path: Path) -> None:
    input_wav = tmp_path / "too-long.wav"
    output_wav = tmp_path / "output.wav"
    input_wav.write_bytes(pcm_to_wav(PcmAudio(pcm=b"\x00\x00" * (16_000 * 15_001 // 1_000))))
    simulator = DeviceSimulator(
        SimulatorConfig(
            bridge_url="ws://127.0.0.1:1/v1/device/ws",
            device_id="sim-001",
            token="test-device-token",  # pragma: allowlist secret
            input_wav=input_wav,
            output_wav=output_wav,
        )
    )

    with pytest.raises(ValueError, match="duration"):
        await simulator.run_voice_turn()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sample_rate", "frames", "channels", "expected_error"),
    [(1, 16, 1, "duration"), (16_000, 2, 8, "sample limit")],
)
async def test_simulator_rejects_oversized_wav_before_decoding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sample_rate: int,
    frames: int,
    channels: int,
    expected_error: str,
) -> None:
    input_wav = tmp_path / "oversized.wav"
    soundfile.write(input_wav, np.zeros((frames, channels)), sample_rate)

    def unexpected_read(*_args: object, **_kwargs: object) -> None:
        pytest.fail("oversized input WAV was decoded before its header was checked")

    monkeypatch.setattr("stackchan_simulator.device.soundfile.read", unexpected_read)
    monkeypatch.setattr("stackchan_simulator.device._MAX_INPUT_SAMPLE_VALUES", 8, raising=False)
    simulator = DeviceSimulator(
        SimulatorConfig(
            bridge_url="ws://127.0.0.1:1/v1/device/ws",
            device_id="sim-001",
            token="test-device-token",  # pragma: allowlist secret
            input_wav=input_wav,
            output_wav=tmp_path / "output.wav",
        )
    )

    with pytest.raises(ValueError, match=expected_error):
        await simulator.run_voice_turn()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("output_limit_ms", "end_reason", "disconnect_between_segments"),
    [
        (60, "completed", False),
        (120, "completed", False),
        (120, "completed", True),
        (120, "cancelled", False),
        (120, "barge_in", False),
        (120, "tts_error", False),
        (120, "device_error", False),
        (120, "disconnect", False),
    ],
)
async def test_simulator_streams_input_wav_in_real_time_and_records_bridge_output_wav(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_limit_ms: int,
    end_reason: str,
    disconnect_between_segments: bool,
) -> None:
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "output.wav"
    input_wav.write_bytes(pcm_to_wav(PcmAudio(pcm=sine_pcm(120))))
    received_packets: list[bytes] = []
    pacing_delays: list[float] = []

    async def record_pacing(delay: float) -> None:
        pacing_delays.append(delay)

    monkeypatch.setattr("stackchan_simulator.device.async_sleep", record_pacing)
    monkeypatch.setattr("stackchan_simulator.device._OUTPUT_SEGMENT_GRACE_SECONDS", 0.01)
    monkeypatch.setattr(
        "stackchan_simulator.device._MAX_OUTPUT_PCM_BYTES",
        16_000 * 2 * output_limit_ms // 1_000,
        raising=False,
    )

    async def handler(connection: ServerConnection) -> None:
        hello = parse_text_frame(await connection.recv())
        assert isinstance(hello, HelloMessage)
        acknowledgement = HelloAckMessage.model_validate(
            {
                "v": 1,
                "type": "hello_ack",
                "message_id": "519a16ce-3a07-4ab6-9767-f39bcc096cb8",
                "sent_at_ms": 1,
                "payload": {
                    "connection_id": "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
                    "selected_protocol_version": 1,
                    "heartbeat_interval_ms": 15_000,
                    "max_command_timeout_ms": 5_000,
                    "server_version": "0.1.0",
                },
            }
        )
        await connection.send(acknowledgement.model_dump_json())
        start = parse_text_frame(await connection.recv())
        assert isinstance(start, AudioInputStartMessage)
        while True:
            incoming = await connection.recv()
            if isinstance(incoming, bytes):
                received_packets.append(incoming)
                continue
            end = parse_text_frame(incoming)
            assert isinstance(end, AudioInputEndMessage)
            assert end.turn_id == start.turn_id
            break
        output_start = AudioOutputStartMessage.model_validate(
            {
                "v": 1,
                "type": "audio.output.start",
                "message_id": "f493e573-cf9b-4d57-bc9d-1dd18ec49529",
                "turn_id": start.turn_id,
                "stream_id": "12c6e18c-9bc6-4c98-978f-992818ff8d1c",
                "sent_at_ms": 2,
                "payload": {
                    "codec": "opus",
                    "sample_rate": 16_000,
                    "channels": 1,
                    "frame_ms": 60,
                    "expected_duration_ms": 60,
                },
            }
        )
        await connection.send(output_start.model_dump_json())
        codec = OpusCodec(OpusCodecConfig(frame_ms=60))
        await connection.send(codec.encode(sine_pcm(60)))
        output_end = AudioOutputEndMessage.model_validate(
            {
                "v": 1,
                "type": "audio.output.end",
                "message_id": "d45f6c3a-bd7e-4795-be42-d7e02ccac051",
                "turn_id": start.turn_id,
                "stream_id": output_start.stream_id,
                "sent_at_ms": 3,
                "payload": {"reason": end_reason},
            }
        )
        await connection.send(output_end.model_dump_json())
        if disconnect_between_segments:
            return
        if end_reason != "completed":
            await connection.wait_closed()
            return
        await sleep(0.02)
        second_start = AudioOutputStartMessage.model_validate(
            {
                **output_start.model_dump(mode="json"),
                "message_id": "9bd9d3a8-ff72-486d-aea1-3f288823a43e",
                "stream_id": "2fd6aeb2-d0dc-4010-ac10-868f7af990f2",
                "sent_at_ms": 4,
            }
        )
        await connection.send(second_start.model_dump_json())
        await connection.send(codec.encode(sine_pcm(60)))
        second_end = AudioOutputEndMessage.model_validate(
            {
                **output_end.model_dump(mode="json"),
                "message_id": "1ea389d9-c044-46c2-bf72-f3c6900cb73f",
                "stream_id": second_start.stream_id,
                "sent_at_ms": 5,
            }
        )
        try:
            await connection.send(second_end.model_dump_json())
        except ConnectionClosed:
            assert output_limit_ms == 60
        await connection.wait_closed()

    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        simulator = DeviceSimulator(
            SimulatorConfig(
                bridge_url=f"ws://127.0.0.1:{port}/v1/device/ws",
                device_id="sim-001",
                token="test-device-token",  # pragma: allowlist secret
                input_wav=input_wav,
                output_wav=output_wav,
                output_segment_grace_seconds=0.05,
            )
        )
        if disconnect_between_segments:
            with pytest.raises(ConnectionClosed):
                await simulator.run_voice_turn()
            assert not output_wav.exists()
            return
        if end_reason != "completed":
            with pytest.raises(ProtocolMessageError, match=end_reason):
                await simulator.run_voice_turn()
            assert not output_wav.exists()
            return
        if output_limit_ms == 60:
            with pytest.raises(ProtocolMessageError, match="PCM"):
                await simulator.run_voice_turn()
            assert not output_wav.exists()
            return
        result = await simulator.run_voice_turn()

    output_samples, output_rate = soundfile.read(output_wav, dtype="int16")
    assert result.input_packets == 2
    assert result.output_packets == 2
    assert result.output_streams == 2
    assert len(received_packets) == 2
    assert pacing_delays == [0.06]
    assert output_rate == 16_000
    assert len(output_samples) == 1_920


@pytest.mark.parametrize("termination", ["timeout", "disconnect", "continuous"])
@pytest.mark.parametrize("stream_number", [1, 2])
@pytest.mark.asyncio
async def test_simulator_rejects_a_truncated_output_stream(
    tmp_path: Path,
    termination: str,
    stream_number: int,
) -> None:
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "truncated-output.wav"
    input_wav.write_bytes(pcm_to_wav(PcmAudio(pcm=sine_pcm(60))))

    async def handler(connection: ServerConnection) -> None:
        hello = parse_text_frame(await connection.recv())
        assert isinstance(hello, HelloMessage)
        acknowledgement = HelloAckMessage.model_validate(
            {
                "v": 1,
                "type": "hello_ack",
                "message_id": "519a16ce-3a07-4ab6-9767-f39bcc096cb8",
                "sent_at_ms": 1,
                "payload": {
                    "connection_id": "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
                    "selected_protocol_version": 1,
                    "heartbeat_interval_ms": 15_000,
                    "max_command_timeout_ms": 5_000,
                    "server_version": "0.1.0",
                },
            }
        )
        await connection.send(acknowledgement.model_dump_json())
        input_start = parse_text_frame(await connection.recv())
        assert isinstance(input_start, AudioInputStartMessage)
        while True:
            incoming = await connection.recv()
            if isinstance(incoming, bytes):
                continue
            assert isinstance(parse_text_frame(incoming), AudioInputEndMessage)
            break

        first_start = AudioOutputStartMessage.model_validate(
            {
                "v": 1,
                "type": "audio.output.start",
                "message_id": "f493e573-cf9b-4d57-bc9d-1dd18ec49529",
                "turn_id": input_start.turn_id,
                "stream_id": "12c6e18c-9bc6-4c98-978f-992818ff8d1c",
                "sent_at_ms": 2,
                "payload": {
                    "codec": "opus",
                    "sample_rate": 16_000,
                    "channels": 1,
                    "frame_ms": 60,
                    "expected_duration_ms": 60,
                },
            }
        )
        codec = OpusCodec(OpusCodecConfig(frame_ms=60))
        await connection.send(first_start.model_dump_json())
        await connection.send(codec.encode(sine_pcm(60)))
        if stream_number == 2:
            await connection.send(
                AudioOutputEndMessage.model_validate(
                    {
                        "v": 1,
                        "type": "audio.output.end",
                        "message_id": "d45f6c3a-bd7e-4795-be42-d7e02ccac051",
                        "turn_id": input_start.turn_id,
                        "stream_id": first_start.stream_id,
                        "sent_at_ms": 3,
                        "payload": {"reason": "completed"},
                    }
                ).model_dump_json()
            )
            second_start = AudioOutputStartMessage.model_validate(
                {
                    **first_start.model_dump(mode="json"),
                    "message_id": "9bd9d3a8-ff72-486d-aea1-3f288823a43e",
                    "stream_id": "2fd6aeb2-d0dc-4010-ac10-868f7af990f2",
                    "sent_at_ms": 4,
                }
            )
            await connection.send(second_start.model_dump_json())
            await connection.send(codec.encode(sine_pcm(60)))
        if termination == "timeout":
            await connection.wait_closed()
        elif termination == "continuous":
            try:
                while True:
                    await sleep(0.005)
                    await connection.send(codec.encode(sine_pcm(60)))
            except ConnectionClosed:
                pass

    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        simulator = DeviceSimulator(
            SimulatorConfig(
                bridge_url=f"ws://127.0.0.1:{port}/v1/device/ws",
                device_id="sim-001",
                token="test-device-token",  # pragma: allowlist secret
                input_wav=input_wav,
                output_wav=output_wav,
                output_segment_grace_seconds=0.01,
            )
        )
        expected_error = ConnectionClosed if termination == "disconnect" else ProtocolMessageError
        with pytest.raises(expected_error):
            await wait_for(simulator.run_voice_turn(), timeout=1)

    assert not output_wav.exists()


@pytest.mark.asyncio
async def test_simulator_completes_real_gateway_vad_hermes_tts_voice_turn(
    tmp_path: Path,
) -> None:
    token = "full-flow-device-token"  # pragma: allowlist secret
    api_key = "full-flow-hermes-key"  # pragma: allowlist secret
    environment = {
        "STACKCHAN_DEVICE_TOKEN": token,
        "HERMES_API_KEY": api_key,  # pragma: allowlist secret
    }
    settings = load_settings(
        ROOT / "config.example.toml",
        environment=environment,
        cli_overrides={
            "captures": {"directory": str(tmp_path / "captures")},
            "hermes": {"model": "hermes-agent"},
            "audio": {"max_recording_ms": 2_000},
            "vad": {
                "start_speech_ms": 60,
                "end_silence_ms": 120,
                "minimum_speech_ms": 120,
                "preroll_ms": 60,
            },
        },
    )
    runtime = build_runtime(
        settings,
        environment=environment,
        hermes_transport=httpx.ASGITransport(
            app=create_mock_hermes_app(
                MockHermesConfig(api_key=api_key, response_text="応答です。")
            )
        ),
    )
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = Server(
        Config(
            runtime.gateway,
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
        raise RuntimeError("test gateway did not start")

    input_wav = tmp_path / "full-input.wav"
    output_wav = tmp_path / "full-output.wav"
    speech = sine_pcm(180)
    silence = b"\x00\x00" * (16_000 * 240 // 1_000)
    input_wav.write_bytes(pcm_to_wav(PcmAudio(pcm=speech + silence)))
    try:
        simulator = DeviceSimulator(
            SimulatorConfig(
                bridge_url=f"ws://127.0.0.1:{port}/v1/device/ws",
                device_id="sim-001",
                token=token,
                input_wav=input_wav,
                output_wav=output_wav,
                output_segment_grace_seconds=0.1,
            )
        )
        result = await simulator.run_voice_turn()
    finally:
        server.should_exit = True
        await server_task
        await runtime.aclose()

    output_samples, output_rate = soundfile.read(output_wav, dtype="int16")
    assert result.input_packets == 7
    assert result.output_packets > 0
    assert result.output_streams == 1
    assert output_rate == 16_000
    assert len(output_samples) > 0
