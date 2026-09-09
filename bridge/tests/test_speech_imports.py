from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "module",
    [
        "stackchan_bridge.turns.speech",
        "stackchan_bridge.mcp_server.server",
        "stackchan_bridge.mcp_server.control_client",
    ],
)
def test_speech_consumers_import_without_initializing_control_api(module: str) -> None:
    # A fresh interpreter prevents earlier tests from hiding import-order cycles.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib, sys; importlib.import_module(sys.argv[1]); "
            "assert 'stackchan_bridge.control.application' not in sys.modules",
            module,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
