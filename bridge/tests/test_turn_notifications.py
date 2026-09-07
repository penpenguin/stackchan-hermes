from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import pytest
from stackchan_bridge.turns.notifications import (
    DeviceTurnFailureNotifier,
    DeviceTurnProgressNotifier,
)


class RecordingCommandSender:
    def __init__(self) -> None:
        self.commands: list[tuple[str, str, Mapping[str, object], UUID | None]] = []

    async def send_command(
        self,
        device_id: str,
        name: str,
        args: Mapping[str, object],
        *,
        turn_id: UUID | None = None,
    ) -> object:
        self.commands.append((device_id, name, args, turn_id))
        return object()


@pytest.mark.asyncio
async def test_failure_notifier_displays_only_a_short_fixed_message() -> None:
    sender = RecordingCommandSender()
    notifier = DeviceTurnFailureNotifier(sender)

    await notifier.notify_failure("sim-001", error_code="EMPTY_TRANSCRIPT")

    assert sender.commands == [
        (
            "sim-001",
            "display.show_text",
            {
                "text": "NO SPEECH",
                "duration_ms": 3_000,
                "priority": 8,
            },
            None,
        )
    ]


@pytest.mark.parametrize(
    ("error_code", "expected_text"),
    [
        ("HERMES_FAILED", "HERMES OFFLINE"),
        ("TTS_FAILED", "TTS OFFLINE"),
        ("EMPTY_TRANSCRIPT", "NO SPEECH"),
        ("STT_TIMEOUT", "STT TIMEOUT"),
        ("STT_FAILED", "STT OFFLINE"),
        ("EMPTY_RESPONSE", "NO RESPONSE"),
        ("TTS_TIMEOUT", "TTS TIMEOUT"),
        ("UNKNOWN", "TURN ERROR"),
    ],
)
@pytest.mark.asyncio
async def test_failure_notifier_uses_text_supported_by_the_physical_toast_font(
    error_code: str,
    expected_text: str,
) -> None:
    sender = RecordingCommandSender()
    notifier = DeviceTurnFailureNotifier(sender)

    await notifier.notify_failure("sim-001", error_code=error_code)

    assert sender.commands[0][2]["text"] == expected_text
    assert expected_text.isascii()
    assert expected_text.isprintable()


@pytest.mark.asyncio
async def test_progress_notifier_uses_only_enabled_turn_owned_automation() -> None:
    sender = RecordingCommandSender()
    notifier = DeviceTurnProgressNotifier(
        sender,
        expression_enabled=True,
        led_enabled=True,
    )
    turn_id = UUID("168b58ca-7c31-4744-b445-d2f20c9bdde0")

    await notifier.notify_tool_started(
        "sim-001",
        turn_id=turn_id,
        tool_name="stackchan_get_status",
    )
    await notifier.notify_tool_completed(
        "sim-001",
        turn_id=turn_id,
        tool_name="stackchan_get_status",
    )

    assert sender.commands == [
        (
            "sim-001",
            "avatar.set_expression",
            {"expression": "thinking"},
            turn_id,
        ),
        (
            "sim-001",
            "led.set_all",
            {"r": 32, "g": 64, "b": 255},
            turn_id,
        ),
        (
            "sim-001",
            "avatar.set_expression",
            {"expression": "idle"},
            turn_id,
        ),
        (
            "sim-001",
            "led.clear",
            {},
            turn_id,
        ),
    ]
