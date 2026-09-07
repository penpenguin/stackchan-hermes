from __future__ import annotations

import ast
import os
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "script",
    [
        "scripts/bootstrap-check.sh",
        "scripts/backup-firmware.sh",
        "scripts/create-debug-report.sh",
        "scripts/run-simulator-e2e.sh",
        "scripts/verify-host.sh",
        "scripts/verify-firmware.sh",
        "scripts/verify.sh",
    ],
)
def test_shell_entrypoints_are_valid_bash(script: str) -> None:
    result = subprocess.run(
        ["bash", "-n", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_verify_host_contains_the_documented_quality_gate() -> None:
    script = (ROOT / "scripts/verify-host.sh").read_text(encoding="utf-8")
    expected_commands = (
        "uv lock --check",
        "uv run ruff format --check .",
        "uv run ruff check .",
        "uv run mypy bridge/src simulator/src",
        "uv run pytest",
        "--cov-fail-under=85",
        "python scripts/validate-protocol.py",
        "python scripts/check-secrets.py",
        "uv run pip-audit",
        "--cache-dir",
        "--skip-editable",
        "PIP_CACHE_DIR",
        "stackchan-bridge doctor --offline",
    )
    for command in expected_commands:
        assert command in script

    with (ROOT / "pyproject.toml").open("rb") as project_file:
        project = tomllib.load(project_file)
    assert project["tool"]["coverage"]["report"]["precision"] == 2


def test_firmware_backup_script_requires_a_complete_read_only_factory_dump() -> None:
    script = (ROOT / "scripts/backup-firmware.sh").read_text(encoding="utf-8")

    assert "read_flash" in script
    assert "0x1000000" in script
    assert "partition-table.bin" in script
    assert "--partition-offset" in script
    assert "--partition-size" in script
    assert "--execute-read" in script
    assert "shasum -a 256" in script
    assert "16777216" in script
    write_lines = [line.strip() for line in script.splitlines() if "write_flash" in line]
    assert write_lines
    assert all(line.startswith("echo ") for line in write_lines)


def test_firmware_backup_uses_bounded_verified_reads_for_native_usb(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    esptool_log = tmp_path / "esptool.log"
    fake_esptool = fake_bin / "esptool.py"
    fake_esptool.write_text(
        """#!/usr/bin/env python3
import os
import sys
from pathlib import Path

arguments = sys.argv[1:]
read_index = arguments.index("read_flash")
address = arguments[read_index + 1]
size = int(arguments[read_index + 2], 0)
output = Path(arguments[read_index + 3])
with Path(os.environ["ESPTOOL_LOG"]).open("a", encoding="utf-8") as log_file:
    log_file.write(" ".join(arguments) + "\\n")
failure_marker = Path(os.environ["ESPTOOL_FAIL_ONCE_MARKER"])
if address == "0x200000" and not failure_marker.exists():
    failure_marker.touch()
    sys.exit(2)
with output.open("wb") as output_file:
    output_file.truncate(size)
""",
        encoding="utf-8",
    )
    fake_esptool.chmod(0o755)
    boot_log = tmp_path / "factory-boot.log"
    boot_log.write_text("factory boot log\n", encoding="utf-8")
    output_dir = tmp_path / "backup"
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["ESPTOOL_LOG"] = str(esptool_log)
    environment["ESPTOOL_FAIL_ONCE_MARKER"] = str(tmp_path / "fail-once.marker")

    result = subprocess.run(
        [
            "bash",
            "scripts/backup-firmware.sh",
            "--port",
            "/dev/null",
            "--output-dir",
            str(output_dir),
            "--boot-log",
            str(boot_log),
            "--firmware-version",
            "1.4.4",
            "--partition-offset",
            "0x8000",
            "--partition-size",
            "0xC00",
            "--execute-read",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    calls = esptool_log.read_text(encoding="utf-8").splitlines()
    factory_calls = calls[:-1]
    expected_offsets = [hex(chunk_index * 0x100000) for chunk_index in range(16)]
    expected_offsets.insert(3, "0x200000")
    assert len(factory_calls) == 17
    for expected_offset, call in zip(expected_offsets, factory_calls, strict=True):
        arguments = call.split()
        read_index = arguments.index("read_flash")
        assert arguments[read_index + 1] == expected_offset
        assert arguments[read_index + 2] == "0x100000"
        assert "--before default_reset" in call
        assert "--after no_reset" in call
        assert "--no-progress" in call

    partition_call = calls[-1]
    assert "read_flash 0x8000 0xC00" in partition_call
    assert "--before default_reset" in partition_call
    assert "--after hard_reset" in partition_call

    factory_images = [
        path for path in output_dir.glob("factory-*.bin") if not path.name.endswith(".sha256")
    ]
    assert len(factory_images) == 1
    assert factory_images[0].stat().st_size == 0x1000000


def test_service_examples_restart_with_backoff_and_keep_secrets_out_of_manifests() -> None:
    launchd = (ROOT / "examples/launchd/com.stackchan-hermes.bridge.plist").read_text(
        encoding="utf-8"
    )
    systemd = (ROOT / "examples/systemd/stackchan-hermes-bridge.service").read_text(
        encoding="utf-8"
    )

    assert "KeepAlive" in launchd
    assert "ThrottleInterval" in launchd
    assert "stackchan-bridge-wrapper.sh" in launchd
    assert "Restart=on-failure" in systemd
    assert "RestartSec=10" in systemd
    assert "EnvironmentFile=" in systemd
    assert (
        "Environment=STACKCHAN_CAPTURES__DIRECTORY=%h/.local/share/stackchan-hermes/captures"
    ) in systemd
    assert (
        "Environment=STACKCHAN_AUDIO__DEBUG_DIRECTORY=%h/.local/state/stackchan-hermes/debug-audio"
    ) in systemd
    for manifest in (launchd, systemd):
        assert "HERMES_API_KEY=" not in manifest
        assert "STACKCHAN_DEVICE_TOKEN=" not in manifest


@pytest.mark.parametrize(
    "script",
    [
        "scripts/generate-device-token.py",
        "scripts/hardware-reconnect-observer.py",
        "scripts/hardware-smoke-test.py",
    ],
)
def test_python_operational_entrypoints_are_valid(script: str) -> None:
    source = (ROOT / script).read_text(encoding="utf-8")

    ast.parse(source, filename=script)


def test_operational_entrypoints_preserve_safe_boundaries() -> None:
    token_script = (ROOT / "scripts/generate-device-token.py").read_text(encoding="utf-8")
    reconnect_script = (ROOT / "scripts/hardware-reconnect-observer.py").read_text(encoding="utf-8")
    smoke_script = (ROOT / "scripts/hardware-smoke-test.py").read_text(encoding="utf-8")
    simulator_script = (ROOT / "scripts/run-simulator-e2e.sh").read_text(encoding="utf-8")

    assert '"token", "create"' in token_script
    assert "client.get(" in reconnect_script
    assert "client.post(" not in reconnect_script
    assert '"firmware_reboot": "not_determined"' in reconnect_script
    assert '"display_confirmation": "required"' in reconnect_script
    assert "--safe-visual" in smoke_script
    assert "--restore-brightness" in smoke_script
    assert "safe visual check requires the physical head lock" in smoke_script
    assert "avatar.set_expression" in smoke_script
    assert "led.set_all" in smoke_script
    assert "display.set_brightness" in smoke_script
    assert "--allow-motion" in smoke_script
    assert "head.set_angles" in smoke_script
    assert "firmware/backups" in smoke_script
    assert "simulator/tests/test_voice_flow.py" in simulator_script
    assert "simulator/tests/test_bridge_integration.py" in simulator_script
