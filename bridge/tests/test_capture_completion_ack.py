from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from stackchan_bridge.captures.store import CaptureStore
from stackchan_bridge.device_gateway.application import (
    DeviceGatewayConfig,
    create_device_gateway_app,
)
from stackchan_bridge.security.tokens import hash_device_token

from .test_device_gateway import hello_message


@pytest.mark.parametrize("known_capture", [False, True])
def test_gateway_completion_ack_matches_the_wire_schema(
    tmp_path: Path, known_capture: bool
) -> None:
    protocol = Path(__file__).resolve().parents[2] / "protocol"
    common_schema = json.loads((protocol / "common.schema.json").read_text())
    validator = Draft202012Validator(
        json.loads((protocol / "control.schema.json").read_text()),
        registry=Registry().with_resource(
            common_schema["$id"], Resource.from_contents(common_schema)
        ),
        format_checker=FormatChecker(),
    )
    store = CaptureStore(
        directory=tmp_path, ttl_seconds=600, max_bytes=2_097_152, monotonic_clock=lambda: 0.0
    )
    capture_id = store.reserve("sim-001").capture_id if known_capture else uuid4()
    token = "simulator-device-token"  # pragma: allowlist secret
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        capture_store=store,
    )
    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/device/ws",
            headers={
                "Authorization": f"Bearer {token}",
                "X-StackChan-Device-Id": "sim-001",
            },
        ) as websocket,
    ):
        websocket.send_json(hello_message().model_dump(mode="json", exclude_none=True))
        assert websocket.receive_json()["type"] == "hello_ack"
        websocket.send_json(
            {
                "v": 1,
                "type": "event",
                "message_id": str(uuid4()),
                "device_id": "sim-001",
                "sent_at_ms": 1,
                "payload": {
                    "name": "camera.completed",
                    "data": {
                        "capture_id": str(capture_id),
                        "ok": True,
                        "sha256": "0" * 64,
                        "size_bytes": 128,
                    },
                },
            }
        )
        ack = websocket.receive_json()

    assert ack["type"] == "camera.completed_ack"
    assert ack["payload"] == {"capture_id": str(capture_id), "accepted": known_capture}
    validator.validate(ack)
