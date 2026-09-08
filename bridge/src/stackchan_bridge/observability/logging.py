"""Allow-listed structured logging that never serializes arbitrary record extras."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_IDENTIFIER_FIELDS = (
    "device_id",
    "connection_id",
    "turn_id",
    "stream_id",
    "request_id",
    "capture_id",
)


class StructuredJsonFormatter(logging.Formatter):
    """Serialize only documented diagnostic fields, with opt-in transcript output."""

    def __init__(self, *, privacy_debug_transcripts: bool) -> None:
        super().__init__()
        self._privacy_debug_transcripts = privacy_debug_transcripts

    def format(self, record: logging.LogRecord) -> str:
        component = _bounded_text(getattr(record, "component", record.name), maximum=128)
        event = _bounded_text(getattr(record, "event", "log"), maximum=128)
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "component": component,
            "event": event,
        }
        for field_name in _IDENTIFIER_FIELDS:
            value = _bounded_text(getattr(record, field_name, None), maximum=256)
            if value is not None:
                payload[field_name] = value
        duration = getattr(record, "duration_ms", None)
        if isinstance(duration, int | float) and not isinstance(duration, bool):
            payload["duration_ms"] = duration
        error_code = _bounded_text(getattr(record, "error_code", None), maximum=64)
        if error_code is not None:
            payload["error_code"] = error_code
        for field_name in ("stage", "reason"):
            value = _bounded_text(getattr(record, field_name, None), maximum=64)
            if value is not None:
                payload[field_name] = value
        image_saved = getattr(record, "image_saved", None)
        if isinstance(image_saved, bool):
            payload["image_saved"] = image_saved
        if self._privacy_debug_transcripts:
            transcript = _bounded_text(getattr(record, "transcript", None), maximum=2_000)
            if transcript is not None:
                payload["transcript"] = transcript
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class SafeTextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        component = _bounded_text(getattr(record, "component", record.name), maximum=128)
        event = _bounded_text(getattr(record, "event", "log"), maximum=128)
        return f"{record.levelname} {component} {event}"


def configure_bridge_logging(
    *,
    level: str,
    json_logs: bool,
    privacy_debug_transcripts: bool,
) -> None:
    """Configure only the package logger and keep protocol stdout untouched."""

    logger = logging.getLogger("stackchan_bridge")
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    if json_logs:
        handler.setFormatter(
            StructuredJsonFormatter(
                privacy_debug_transcripts=privacy_debug_transcripts,
            )
        )
    else:
        handler.setFormatter(SafeTextFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


def _bounded_text(value: object, *, maximum: int) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value[:maximum]
