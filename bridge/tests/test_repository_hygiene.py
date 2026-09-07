from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_readme_links_to_hardware_evidence_without_inline_completion_status() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Current status" not in readme
    assert re.search(r"\b(?:HW-\d+|CAM-\d+)\b", readme) is None
    for report in ("hardware-test-report.md", "verification-report.md"):
        assert f"](docs/{report})" in readme

    report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    normalized = " ".join(report.split())

    assert "HW-01 through HW-13 are PASS" in normalized
    assert "CAM-002 live physical vision turn is PASS" in normalized
    assert "| HW-04 Body | **PASS** |" in report


def test_public_documentation_omits_machine_local_identifiers() -> None:
    documents = [ROOT / "README.md", *(ROOT / "docs").rglob("*.md")]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in documents)

    for machine_local_pattern in (
        r"(?<![A-Za-z0-9._/-])/home/(?!REPLACE_ME(?:/|\b))[^/\s]+/",
        r"(?<![A-Za-z0-9._/-])/Users/(?!REPLACE_ME(?:/|\b))[^/\s]+/",
        r"USB bus `\d+(?:-\d+)+`",
        r"Hermes[^\n]{0,100}\bon `[^`]+`",
        r"`[^`]+` のloopback限定",
        r"/dev/serial/by-id/(?!REVIEWED-ID(?:\b|/))[^\s`]+",
    ):
        assert re.search(machine_local_pattern, combined) is None


def test_current_documents_do_not_retain_completed_work_as_in_progress() -> None:
    plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    operations = (ROOT / "docs" / "operations.md").read_text(encoding="utf-8")

    assert "**In progress (" not in plan
    assert "live STT/provider behavior remains unverified" not in requirements
    assert "live provider quality remains unverified" not in requirements
    assert "Live `input_image` remains CAM-002 work" not in requirements
    assert "live latency values unavailable" not in requirements
    assert "## Current host snapshot" not in operations


def test_common_machine_local_artifacts_are_ignored() -> None:
    def ignored(path: str) -> bool:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", path],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode in {0, 1}
        return result.returncode == 0

    for path in (
        "scratch/session.log",
        "scratch/result.tmp",
        "scratch/result.temp",
        "scratch/notes.bak",
        "scratch/merge.orig",
        "scratch/editor.swp",
        "scratch/editor.swo",
        "scratch/file~",
        ".cache/tool/state.json",
    ):
        assert ignored(path), path
