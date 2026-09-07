#!/usr/bin/env python3
"""Fail when detect-secrets reports an unreviewed repository finding."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / ".secrets.baseline"
EXCLUDED_PATHS = (
    r"(^|/)(\.git|\.venv|\.mypy_cache|\.pytest_cache|\.ruff_cache|__pycache__|"
    r"\.secrets\.baseline|uv\.lock|"
    r"firmware/(backups|build(?:-[A-Za-z0-9_.-]+)?|managed_components|xiaozhi-esp32)|"
    r"firmware/sdkconfig(\.old)?|"
    r"firmware/components/(ArduinoJson|esp-now|mooncake|mooncake_log|smooth_ui_toolkit))(/|$)"
)


def _repository_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("git could not enumerate repository files")
    excluded = re.compile(EXCLUDED_PATHS)
    return sorted(
        path for path in result.stdout.split("\0") if path and excluded.search(path) is None
    )


def main() -> int:
    executable = shutil.which("detect-secrets-hook")
    if executable is None:
        print("ERROR: detect-secrets is not installed")
        return 2
    if not BASELINE.is_file():
        print("ERROR: reviewed secret baseline is missing")
        return 2

    try:
        repository_files = _repository_files()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2
    result = subprocess.run(
        [executable, "--baseline", str(BASELINE), "--json", *repository_files],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Potential secrets require review:")
        print(result.stdout, end="")
        print(result.stderr, end="")
        return result.returncode

    print("No potential secrets found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
