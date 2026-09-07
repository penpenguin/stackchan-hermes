from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/hardware-smoke-test.py"


class FakeResponse:
    def __init__(self, payload: dict[str, Any], *, failed: bool = False) -> None:
        self._payload = payload
        self._failed = failed

    def raise_for_status(self) -> None:
        if self._failed:
            raise httpx.HTTPError("injected command failure")

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeClient:
    def __init__(
        self,
        *,
        fail_at_call: int | None = None,
        head_capability: bool = False,
        command_ok: bool = True,
        **_: object,
    ) -> None:
        self.commands: list[dict[str, Any]] = []
        self._fail_at_call = fail_at_call
        self._head_capability = head_capability
        self._command_ok = command_ok

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get(self, path: str) -> FakeResponse:
        assert path == "/v1/control/devices/stackchan-001"
        return FakeResponse(
            {
                "device_id": "stackchan-001",
                "hardware_model": "M5STACK-K151",
                "capabilities": {
                    "avatar": True,
                    "display": True,
                    "head": self._head_capability,
                    "led_count": 12,
                },
            }
        )

    def post(self, path: str, *, json: dict[str, Any]) -> FakeResponse:
        assert path == "/v1/control/devices/stackchan-001/commands"
        self.commands.append(json)
        return FakeResponse(
            {"ok": self._command_ok},
            failed=len(self.commands) == self._fail_at_call,
        )


@pytest.fixture
def smoke_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("hardware_smoke_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_safe_visual_smoke_applies_and_restores_without_head_commands(
    monkeypatch: pytest.MonkeyPatch,
    smoke_module: ModuleType,
) -> None:
    client = FakeClient()
    monkeypatch.setattr(smoke_module.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hardware-smoke-test.py",
            "--device-id",
            "stackchan-001",
            "--safe-visual",
            "--restore-brightness",
            "70",
            "--hold-seconds",
            "0",
        ],
    )

    assert smoke_module.main() == 0
    assert client.commands == [
        {"name": "avatar.set_expression", "args": {"expression": "happy"}},
        {"name": "led.set_all", "args": {"r": 0, "g": 16, "b": 64}},
        {"name": "display.set_brightness", "args": {"brightness": 35}},
        {"name": "display.set_brightness", "args": {"brightness": 70}},
        {"name": "led.clear", "args": {}},
        {"name": "avatar.set_expression", "args": {"expression": "idle"}},
    ]
    assert all(not command["name"].startswith("head.") for command in client.commands)


def test_safe_visual_smoke_rejects_negative_results_and_attempts_every_restore(
    monkeypatch: pytest.MonkeyPatch,
    smoke_module: ModuleType,
) -> None:
    client = FakeClient(command_ok=False)
    monkeypatch.setattr(smoke_module.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hardware-smoke-test.py",
            "--device-id",
            "stackchan-001",
            "--safe-visual",
            "--restore-brightness",
            "70",
            "--hold-seconds",
            "0",
        ],
    )

    assert smoke_module.main() == 1
    assert [command["name"] for command in client.commands] == [
        "avatar.set_expression",
        "display.set_brightness",
        "led.clear",
        "avatar.set_expression",
    ]


def test_safe_visual_smoke_attempts_every_restore_after_one_restore_fails(
    monkeypatch: pytest.MonkeyPatch,
    smoke_module: ModuleType,
) -> None:
    client = FakeClient(fail_at_call=4)
    monkeypatch.setattr(smoke_module.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hardware-smoke-test.py",
            "--device-id",
            "stackchan-001",
            "--safe-visual",
            "--restore-brightness",
            "70",
            "--hold-seconds",
            "0",
        ],
    )

    assert smoke_module.main() == 1
    assert [command["name"] for command in client.commands] == [
        "avatar.set_expression",
        "led.set_all",
        "display.set_brightness",
        "display.set_brightness",
        "led.clear",
        "avatar.set_expression",
    ]


def test_motion_smoke_requires_unlocked_head_capability_before_any_command(
    monkeypatch: pytest.MonkeyPatch,
    smoke_module: ModuleType,
) -> None:
    client = FakeClient(head_capability=False)
    monkeypatch.setattr(smoke_module.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(smoke_module, "firmware_backup_is_verified", lambda _: True)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hardware-smoke-test.py",
            "--device-id",
            "stackchan-001",
            "--allow-motion",
            "--yaw",
            "0",
            "--pitch",
            "45",
        ],
    )

    with pytest.raises(SystemExit) as error:
        smoke_module.main()

    assert error.value.code == 2
    assert client.commands == []


def test_motion_smoke_sends_one_small_command_for_an_unlocked_verified_k151(
    monkeypatch: pytest.MonkeyPatch,
    smoke_module: ModuleType,
) -> None:
    client = FakeClient(head_capability=True)
    monkeypatch.setattr(smoke_module.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(smoke_module, "firmware_backup_is_verified", lambda _: True)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hardware-smoke-test.py",
            "--device-id",
            "stackchan-001",
            "--allow-motion",
            "--yaw",
            "5",
            "--pitch",
            "45",
        ],
    )

    assert smoke_module.main() == 0
    assert client.commands == [
        {
            "name": "head.set_angles",
            "args": {"yaw": 5.0, "pitch": 45.0, "speed": 10},
        }
    ]


def test_motion_smoke_rejects_a_negative_device_result(
    monkeypatch: pytest.MonkeyPatch,
    smoke_module: ModuleType,
) -> None:
    client = FakeClient(head_capability=True, command_ok=False)
    monkeypatch.setattr(smoke_module.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(smoke_module, "firmware_backup_is_verified", lambda _: True)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hardware-smoke-test.py",
            "--device-id",
            "stackchan-001",
            "--allow-motion",
            "--yaw",
            "5",
            "--pitch",
            "45",
        ],
    )

    assert smoke_module.main() == 1
    assert client.commands == [
        {
            "name": "head.set_angles",
            "args": {"yaw": 5.0, "pitch": 45.0, "speed": 10},
        }
    ]


def test_home_smoke_sends_one_home_command_for_an_unlocked_verified_k151(
    monkeypatch: pytest.MonkeyPatch,
    smoke_module: ModuleType,
) -> None:
    client = FakeClient(head_capability=True)
    monkeypatch.setattr(smoke_module.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(smoke_module, "firmware_backup_is_verified", lambda _: True)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hardware-smoke-test.py",
            "--device-id",
            "stackchan-001",
            "--allow-motion",
            "--home",
        ],
    )

    assert smoke_module.main() == 0
    assert client.commands == [{"name": "head.home", "args": {}}]


def test_home_smoke_rejects_angle_arguments_before_any_command(
    monkeypatch: pytest.MonkeyPatch,
    smoke_module: ModuleType,
) -> None:
    client = FakeClient(head_capability=True)
    monkeypatch.setattr(smoke_module.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(smoke_module, "firmware_backup_is_verified", lambda _: True)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hardware-smoke-test.py",
            "--device-id",
            "stackchan-001",
            "--allow-motion",
            "--home",
            "--yaw",
            "5",
            "--pitch",
            "45",
        ],
    )

    with pytest.raises(SystemExit) as error:
        smoke_module.main()

    assert error.value.code == 2
    assert client.commands == []


def test_home_smoke_requires_explicit_motion_permission(
    monkeypatch: pytest.MonkeyPatch,
    smoke_module: ModuleType,
) -> None:
    client = FakeClient(head_capability=True)
    monkeypatch.setattr(smoke_module.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hardware-smoke-test.py",
            "--device-id",
            "stackchan-001",
            "--home",
        ],
    )

    with pytest.raises(SystemExit) as error:
        smoke_module.main()

    assert error.value.code == 2
    assert client.commands == []
