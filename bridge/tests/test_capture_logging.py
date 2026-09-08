import json
import logging

from stackchan_bridge.observability.logging import StructuredJsonFormatter


def test_camera_diagnostics_survive_structured_logging_without_unlisted_extras():
    record = logging.makeLogRecord(
        {
            "name": "capture",
            "levelname": "WARNING",
            "msg": "unused",
            "capture_id": "11111111-1111-4111-8111-111111111111",
            "stage": "image_saved",
            "reason": "CAPTURE_COMPLETION_TIMEOUT",
            "image_saved": True,
            "duration_ms": 10000,
            "authorization": "never-serialize-this",
            "body": b"image",
        }
    )
    payload = json.loads(StructuredJsonFormatter(privacy_debug_transcripts=False).format(record))
    assert payload["capture_id"] == record.capture_id
    assert payload["stage"] == "image_saved"
    assert payload["reason"] == "CAPTURE_COMPLETION_TIMEOUT"
    assert payload["image_saved"] is True
    assert "authorization" not in payload and "body" not in payload
