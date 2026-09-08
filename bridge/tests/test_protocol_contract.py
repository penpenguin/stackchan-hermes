from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_checked_in_protocol_examples_match_their_schemas() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate-protocol.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "15 valid examples" in result.stdout
    assert "11 expected invalid examples" in result.stdout
