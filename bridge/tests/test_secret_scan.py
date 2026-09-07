from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def _load_secret_scanner() -> ModuleType:
    path = ROOT / "scripts" / "check-secrets.py"
    spec = importlib.util.spec_from_file_location("check_secrets", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_secret_scan_excludes_only_generated_and_locked_external_firmware_trees() -> None:
    scanner = _load_secret_scanner()
    excluded = re.compile(scanner.EXCLUDED_PATHS)

    for path in (
        ".secrets.baseline",
        "firmware/build/stack-chan.bin",
        "firmware/build-hermes-enabled/stack-chan.bin",
        "firmware/build-host-tests/motion_math_test",
        "firmware/managed_components/vendor__component/source.c",
        "firmware/sdkconfig",
        "firmware/sdkconfig.old",
        "firmware/xiaozhi-esp32/main/application.cc",
        "firmware/components/mooncake/src/mooncake.cpp",
        "firmware/components/ArduinoJson/src/ArduinoJson.h",
    ):
        assert excluded.search(path), path

    assert excluded.search("firmware/components/stackchan_bridge_client/client.cpp") is None
    assert excluded.search("firmware/main/main.cpp") is None
    assert scanner.BASELINE == ROOT / ".secrets.baseline"

    repository_files = scanner._repository_files()
    assert "firmware/main/main.cpp" in repository_files
    assert not any(path.startswith("firmware/build-") for path in repository_files)
    assert not any(path.startswith("firmware/managed_components/") for path in repository_files)


def test_repository_secret_scan_has_no_unreviewed_findings() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check-secrets.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "No potential secrets found" in result.stdout
