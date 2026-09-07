from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from stackchan_bridge.observability.reconnect import ReconnectObservation

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/hardware-reconnect-observer.py"


class FakeResponse:
    def __init__(self, *, head: bool = False) -> None:
        self.status_code = 200
        self._head = head

    def json(self) -> dict[str, Any]:
        return {
            "device_id": "stackchan-001",
            "connected": True,
            "hardware_model": "M5STACK-K151",
            "capabilities": {"head": self._head},
        }


class FakeClient:
    def __init__(self, *, head: bool = False, **_: object) -> None:
        self.paths: list[str] = []
        self._head = head

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get(self, path: str) -> FakeResponse:
        self.paths.append(path)
        return FakeResponse(head=self._head)


@pytest.fixture
def observer_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("hardware_reconnect_observer", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_reports_transport_timing_without_claiming_display_or_reboot_evidence(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    observer_module: ModuleType,
) -> None:
    client = FakeClient()
    monkeypatch.setattr(observer_module.httpx, "Client", lambda **_: client)

    def observe(probe: object, **_: object) -> ReconnectObservation:
        assert callable(probe)
        assert probe() is True
        return ReconnectObservation(reconnect_seconds=1.234, loss_confirmations=2)

    monkeypatch.setattr(observer_module, "observe_reconnect", observe)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hardware-reconnect-observer.py",
            "--device-id",
            "stackchan-001",
        ],
    )

    assert observer_module.main() == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "device_id": "stackchan-001",
        "display_confirmation": "required",
        "firmware_reboot": "not_determined",
        "loss_confirmations": 2,
        "reconnect_ms": 1234.0,
        "transport_observed": True,
    }
    assert client.paths == [
        "/v1/control/devices/stackchan-001",
        "/v1/control/devices/stackchan-001",
    ]


def test_cli_refuses_observation_without_the_physical_head_lock(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    observer_module: ModuleType,
) -> None:
    client = FakeClient(head=True)
    monkeypatch.setattr(observer_module.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hardware-reconnect-observer.py",
            "--device-id",
            "stackchan-001",
        ],
    )

    assert observer_module.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "remote response body" in captured.err
    assert client.paths == ["/v1/control/devices/stackchan-001"]
