from __future__ import annotations

import pytest
from pydantic import ValidationError
from stackchan_bridge.protocol.models import CaptureArguments, HelloMessage

from .test_control_api import simulator_hello


def test_old_camera_handshake_is_rejected() -> None:
    data = simulator_hello().model_dump()
    data["payload"].pop("capture_protocol_version", None)
    with pytest.raises(ValidationError):
        HelloMessage.model_validate(data)


def test_capture_requires_a_bounded_time_budget() -> None:
    args = {"capture_id": "db4d04eb-e319-47bb-896b-cd44bc71088d", "quality": 80}
    with pytest.raises(ValidationError):
        CaptureArguments.model_validate(args)
    for value in [0, 120001, True]:
        with pytest.raises(ValidationError):
            CaptureArguments.model_validate({**args, "timeout_ms": value})
    assert CaptureArguments.model_validate({**args, "timeout_ms": 10000}).timeout_ms == 10000
