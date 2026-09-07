"""Best-effort device UI notifications for failed conversational turns."""

from __future__ import annotations

from asyncio import gather
from collections.abc import Mapping
from typing import Protocol
from uuid import UUID


class CommandSender(Protocol):
    async def send_command(
        self,
        device_id: str,
        name: str,
        args: Mapping[str, object],
        *,
        turn_id: UUID | None = None,
    ) -> object: ...


_FAILURE_TEXT = {
    "EMPTY_TRANSCRIPT": "NO SPEECH",
    "STT_TIMEOUT": "STT TIMEOUT",
    "STT_FAILED": "STT OFFLINE",
    "HERMES_FAILED": "HERMES OFFLINE",
    "EMPTY_RESPONSE": "NO RESPONSE",
    "TTS_TIMEOUT": "TTS TIMEOUT",
    "TTS_FAILED": "TTS OFFLINE",
}


class DeviceTurnFailureNotifier:
    """Show bounded fixed text without exposing provider errors or transcripts."""

    def __init__(self, commands: CommandSender) -> None:
        self._commands = commands

    async def notify_failure(self, device_id: str, *, error_code: str) -> None:
        text = _FAILURE_TEXT.get(error_code, "TURN ERROR")
        await self._commands.send_command(
            device_id,
            "display.show_text",
            {
                "text": text,
                "duration_ms": 3_000,
                "priority": 8,
            },
        )


class DeviceTurnProgressNotifier:
    """Render Hermes tool progress through configured, capability-checked commands."""

    def __init__(
        self,
        commands: CommandSender,
        *,
        expression_enabled: bool,
        led_enabled: bool,
    ) -> None:
        self._commands = commands
        self._expression_enabled = expression_enabled
        self._led_enabled = led_enabled

    async def notify_tool_started(
        self,
        device_id: str,
        *,
        turn_id: UUID,
        tool_name: str,
    ) -> None:
        del tool_name
        requests = []
        if self._expression_enabled:
            requests.append(
                self._commands.send_command(
                    device_id,
                    "avatar.set_expression",
                    {"expression": "thinking"},
                    turn_id=turn_id,
                )
            )
        if self._led_enabled:
            requests.append(
                self._commands.send_command(
                    device_id,
                    "led.set_all",
                    {"r": 32, "g": 64, "b": 255},
                    turn_id=turn_id,
                )
            )
        if requests:
            await gather(*requests, return_exceptions=True)

    async def notify_tool_completed(
        self,
        device_id: str,
        *,
        turn_id: UUID,
        tool_name: str,
    ) -> None:
        del tool_name
        requests = []
        if self._expression_enabled:
            requests.append(
                self._commands.send_command(
                    device_id,
                    "avatar.set_expression",
                    {"expression": "idle"},
                    turn_id=turn_id,
                )
            )
        if self._led_enabled:
            requests.append(
                self._commands.send_command(
                    device_id,
                    "led.clear",
                    {},
                    turn_id=turn_id,
                )
            )
        if requests:
            await gather(*requests, return_exceptions=True)
