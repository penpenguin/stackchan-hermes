from pathlib import Path

import pytest
import stackchan_simulator
import stackchan_simulator.cli as simulator_cli
from stackchan_simulator.device import SimulatorConfig, SimulatorFault


def test_package_exposes_initial_version() -> None:
    assert stackchan_simulator.__version__ == "0.1.0"


def test_version_command_prints_version(capsys: object) -> None:
    assert simulator_cli.main(["--version"]) == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert captured.out.strip() == "stackchan-simulator 0.1.0"


def test_no_simulator_arguments_print_help(capsys: object) -> None:
    assert simulator_cli.main([]) == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert captured.out.startswith("usage: stackchan-simulator")


def test_simulator_entrypoint_uses_main_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(simulator_cli, "main", lambda: 9)

    with pytest.raises(SystemExit) as error:
        simulator_cli.entrypoint()

    assert error.value.code == 9


def test_cli_builds_runtime_config_from_named_token_environment() -> None:
    received: list[SimulatorConfig] = []

    exit_code = simulator_cli.main(
        [
            "--bridge",
            "ws://127.0.0.1:8765/v1/device/ws",
            "--device-id",
            "sim-001",
            "--token-env",
            "SIMULATOR_TEST_TOKEN",
            "--input-wav",
            "simulator/fixtures/audio/ja-short.wav",
            "--output-wav",
            "/tmp/stackchan-output.wav",
            "--protocol-version",
            "1",
            "--command-delay-ms",
            "250",
            "--output-segment-grace-ms",
            "45000",
        ],
        environ={"SIMULATOR_TEST_TOKEN": "runtime-only-token"},  # pragma: allowlist secret
        runner=lambda config: received.append(config) or 0,
    )

    assert exit_code == 0
    assert len(received) == 1
    assert received[0].device_id == "sim-001"
    assert received[0].token == "runtime-only-token"  # pragma: allowlist secret
    assert received[0].protocol_versions == (1,)
    assert received[0].command_delay_seconds == 0.25
    assert received[0].output_segment_grace_seconds == 45
    assert "runtime-only-token" not in repr(received[0])


def test_default_runner_selects_voice_flow_when_wav_paths_are_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: object,
) -> None:
    calls: list[str] = []

    class FakeSimulator:
        def __init__(self, _config: SimulatorConfig) -> None:
            pass

        async def handshake(self) -> object:
            calls.append("handshake")
            raise AssertionError("voice mode must not run handshake-only flow")

        async def run_voice_turn(self) -> object:
            calls.append("voice")
            return type(
                "Result",
                (),
                {"input_packets": 2, "output_packets": 3, "output_streams": 1},
            )()

    monkeypatch.setattr(simulator_cli, "DeviceSimulator", FakeSimulator)
    config = SimulatorConfig(
        bridge_url="ws://127.0.0.1:8765/v1/device/ws",
        device_id="sim-001",
        token="runtime-only-token",  # pragma: allowlist secret
        input_wav=tmp_path / "input.wav",
        output_wav=tmp_path / "output.wav",
    )

    assert simulator_cli.run_simulator(config) == 0
    assert calls == ["voice"]
    assert "input_packets=2" in capsys.readouterr().out  # type: ignore[attr-defined]


def test_cli_exposes_a_named_transport_fault_scenario() -> None:
    received: list[SimulatorConfig] = []

    assert (
        simulator_cli.main(
            [
                "--bridge",
                "ws://127.0.0.1:8765/v1/device/ws",
                "--device-id",
                "sim-001",
                "--token-env",
                "SIMULATOR_TEST_TOKEN",
                "--fault",
                "malformed-json",
            ],
            environ={"SIMULATOR_TEST_TOKEN": "runtime-only-token"},  # pragma: allowlist secret
            runner=lambda config: received.append(config) or 0,
        )
        == 0
    )

    assert received[0].fault is SimulatorFault.MALFORMED_JSON


def test_default_runner_selects_the_fault_flow(
    monkeypatch: pytest.MonkeyPatch,
    capsys: object,
) -> None:
    calls: list[SimulatorFault] = []

    class FakeSimulator:
        def __init__(self, _config: SimulatorConfig) -> None:
            pass

        async def run_fault(self, fault: SimulatorFault) -> None:
            calls.append(fault)

    monkeypatch.setattr(simulator_cli, "DeviceSimulator", FakeSimulator)
    config = SimulatorConfig(
        bridge_url="ws://127.0.0.1:8765/v1/device/ws",
        device_id="sim-001",
        token="runtime-only-token",  # pragma: allowlist secret
        fault=SimulatorFault.DISCONNECT,
    )

    assert simulator_cli.run_simulator(config) == 0
    assert calls == [SimulatorFault.DISCONNECT]
    assert "fault injected: disconnect" in capsys.readouterr().out  # type: ignore[attr-defined]
