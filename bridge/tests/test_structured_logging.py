from __future__ import annotations

import json
import logging
from typing import cast
from uuid import UUID

import pytest
from fastapi import WebSocket
from stackchan_bridge.device_gateway.application import DeviceConnection, DeviceRegistry
from stackchan_bridge.observability.logging import (
    StructuredJsonFormatter,
    configure_bridge_logging,
)
from stackchan_bridge.turns.coordinator import TurnCoordinator, TurnState, TurnTrigger

from .test_control_api import simulator_hello


def test_structured_log_is_allow_listed_and_redacts_private_payloads() -> None:
    formatter = StructuredJsonFormatter(privacy_debug_transcripts=False)
    record = logging.makeLogRecord(
        {
            "name": "stackchan_bridge.gateway",
            "levelno": logging.WARNING,
            "levelname": "WARNING",
            "component": "device_gateway",
            "event": "device_rejected",
            "device_id": "sim-001",
            "connection_id": "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
            "duration_ms": 12.5,
            "error_code": "UNAUTHORIZED",
            "api_key": "must-not-appear",  # pragma: allowlist secret
            "device_token": "must-not-appear",  # pragma: allowlist secret
            "transcript": "秘密の会話全文",
            "raw_audio": b"private-audio",
            "image_bytes": b"private-image",
        }
    )

    payload = json.loads(formatter.format(record))
    encoded = json.dumps(payload, ensure_ascii=False)

    assert payload["level"] == "WARNING"
    assert payload["component"] == "device_gateway"
    assert payload["event"] == "device_rejected"
    assert payload["device_id"] == "sim-001"
    assert payload["duration_ms"] == 12.5
    assert payload["error_code"] == "UNAUTHORIZED"
    assert "timestamp" in payload
    assert "must-not-appear" not in encoded
    assert "秘密の会話全文" not in encoded
    assert "private-audio" not in encoded
    assert "private-image" not in encoded


def test_structured_log_allows_bounded_transcript_only_in_privacy_debug_mode() -> None:
    formatter = StructuredJsonFormatter(privacy_debug_transcripts=True)
    record = logging.makeLogRecord(
        {
            "name": "stackchan_bridge.turns",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "event": "stt_completed",
            "transcript": "あ" * 3_000,
        }
    )

    payload = json.loads(formatter.format(record))

    assert payload["transcript"] == "あ" * 2_000


def test_bridge_logging_writes_json_or_safe_text_to_stderr_only(capsys: object) -> None:
    logger = logging.getLogger("stackchan_bridge.test")
    configure_bridge_logging(
        level="INFO",
        json_logs=True,
        privacy_debug_transcripts=False,
    )
    logger.info("ignored message", extra={"event": "json_event", "device_id": "sim-001"})
    first = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(first.err)
    assert first.out == ""
    assert payload["event"] == "json_event"
    assert payload["device_id"] == "sim-001"

    configure_bridge_logging(
        level="WARNING",
        json_logs=False,
        privacy_debug_transcripts=False,
    )
    logger.warning("ignored secret-like message", extra={"event": "safe_event"})
    second = capsys.readouterr()  # type: ignore[attr-defined]
    assert second.out == ""
    assert second.err.strip() == "WARNING stackchan_bridge.test safe_event"


@pytest.mark.asyncio
async def test_registry_emits_safe_connection_lifecycle_events(capsys: object) -> None:
    configure_bridge_logging(
        level="INFO",
        json_logs=True,
        privacy_debug_transcripts=False,
    )
    registry = DeviceRegistry(command_timeout_seconds=5)
    connection_id = UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")

    await registry.register(
        DeviceConnection(
            connection_id=connection_id,
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, object()),
        )
    )
    registry.unregister("sim-001", connection_id)

    captured = capsys.readouterr()  # type: ignore[attr-defined]
    events = [json.loads(line) for line in captured.err.splitlines()]
    assert [event["event"] for event in events] == ["device.connected", "device.disconnected"]
    assert all(event["device_id"] == "sim-001" for event in events)
    assert all(event["connection_id"] == str(connection_id) for event in events)
    assert captured.out == ""


@pytest.mark.asyncio
async def test_turn_coordinator_emits_safe_start_and_completion_events(capsys: object) -> None:
    configure_bridge_logging(
        level="INFO",
        json_logs=True,
        privacy_debug_transcripts=False,
    )
    coordinator = TurnCoordinator()
    turn = await coordinator.begin("sim-001", trigger=TurnTrigger.TOUCH)
    for state in (
        TurnState.TRANSCRIBING,
        TurnState.WAITING_HERMES,
        TurnState.SYNTHESIZING,
        TurnState.PLAYING,
    ):
        await coordinator.transition(turn.turn_id, state)
    await coordinator.complete(turn.turn_id)

    captured = capsys.readouterr()  # type: ignore[attr-defined]
    events = [json.loads(line) for line in captured.err.splitlines()]
    assert [event["event"] for event in events] == ["turn.started", "turn.completed"]
    assert all(event["device_id"] == "sim-001" for event in events)
    assert all(event["turn_id"] == str(turn.turn_id) for event in events)
    assert isinstance(events[-1]["duration_ms"], float)
    assert "transcript" not in captured.err


@pytest.mark.asyncio
async def test_turn_coordinator_emits_a_safe_cancellation_reason(capsys: object) -> None:
    configure_bridge_logging(
        level="INFO",
        json_logs=True,
        privacy_debug_transcripts=False,
    )
    coordinator = TurnCoordinator()
    turn = await coordinator.begin("sim-001", trigger=TurnTrigger.TOUCH)

    assert await coordinator.cancel_device("sim-001", reason="USER_CANCEL") is True

    captured = capsys.readouterr()  # type: ignore[attr-defined]
    events = [json.loads(line) for line in captured.err.splitlines()]
    assert [event["event"] for event in events] == ["turn.started", "turn.cancelled"]
    assert events[-1]["turn_id"] == str(turn.turn_id)
    assert events[-1]["error_code"] == "USER_CANCEL"
    assert isinstance(events[-1]["duration_ms"], float)
