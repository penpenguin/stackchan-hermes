from __future__ import annotations

import pytest
from stackchan_bridge.protocol.models import HelloAckMessage
from stackchan_simulator.device import DeviceSimulator, SimulatorConfig
from stackchan_simulator.reconnect import ReconnectBackoff


def acknowledgement() -> HelloAckMessage:
    return HelloAckMessage.model_validate(
        {
            "v": 1,
            "type": "hello_ack",
            "message_id": "519a16ce-3a07-4ab6-9767-f39bcc096cb8",
            "sent_at_ms": 1,
            "payload": {
                "connection_id": "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
                "capture_protocol_version": 2,
                "selected_protocol_version": 1,
                "heartbeat_interval_ms": 15_000,
                "max_command_timeout_ms": 5_000,
                "server_version": "0.1.0",
            },
        }
    )


def test_reconnect_backoff_is_bounded_and_resets_after_a_stable_connection() -> None:
    backoff = ReconnectBackoff()

    assert [backoff.next_delay_seconds() for _ in range(7)] == [1, 2, 4, 8, 16, 30, 30]

    backoff.record_connection(connected_seconds=29.9)
    assert backoff.next_delay_seconds() == 30

    backoff.record_connection(connected_seconds=30)
    assert backoff.next_delay_seconds() == 1


def test_reconnect_backoff_rejects_invalid_durations() -> None:
    with pytest.raises(ValueError, match="positive"):
        ReconnectBackoff(stable_connection_seconds=0)

    backoff = ReconnectBackoff()
    with pytest.raises(ValueError, match="negative"):
        backoff.record_connection(connected_seconds=-0.1)


@pytest.mark.asyncio
async def test_simulator_retries_transient_handshake_failures_with_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    simulator = DeviceSimulator(
        SimulatorConfig(
            bridge_url="ws://127.0.0.1:8765/v1/device/ws",
            device_id="sim-001",
            token="test-device-token",  # pragma: allowlist secret
        )
    )
    attempts = 0
    delays: list[float] = []

    async def flaky_handshake() -> HelloAckMessage:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise OSError("temporary disconnect")
        return acknowledgement()

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(simulator, "handshake", flaky_handshake)

    result = await simulator.handshake_with_reconnect(max_attempts=3, sleep=record_sleep)

    assert result == acknowledgement()
    assert attempts == 3
    assert delays == [1, 2]


@pytest.mark.asyncio
async def test_simulator_reconnect_attempt_limit_preserves_last_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    simulator = DeviceSimulator(
        SimulatorConfig(
            bridge_url="ws://127.0.0.1:8765/v1/device/ws",
            device_id="sim-001",
            token="test-device-token",  # pragma: allowlist secret
        )
    )
    sleeps: list[float] = []

    async def disconnected() -> HelloAckMessage:
        raise OSError("Bridge remains unavailable")

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(simulator, "handshake", disconnected)

    with pytest.raises(OSError, match="Bridge remains unavailable"):
        await simulator.handshake_with_reconnect(max_attempts=2, sleep=record_sleep)

    assert sleeps == [1]
