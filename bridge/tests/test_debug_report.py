from __future__ import annotations

from pathlib import Path

import pytest
from stackchan_bridge.observability import debug_report
from stackchan_bridge.observability.debug_report import create_debug_report, redact_debug_text

ROOT = Path(__file__).resolve().parents[2]


def test_debug_report_redacts_credentials_and_inline_media(tmp_path: Path) -> None:
    private_log = tmp_path / "bridge.log"
    private_log.write_text(
        "\n".join(
            (
                "Authorization: Bearer private-hermes-token",
                "HERMES_API_KEY=private-api-key",
                '"device_token":"private-device-token"',
                "wifi_password: private-wifi-password",
                "image=data:image/jpeg;base64,/9j/private-image/9k=",
                "event=bridge.ready",
            )
        ),
        encoding="utf-8",
    )
    output = tmp_path / "debug-report.txt"

    create_debug_report(
        output,
        log_paths=(private_log,),
        project_root=tmp_path,
        repository_summary="commit=test\nstatus=clean",
        host_summary="python=available",
    )

    report = output.read_text(encoding="utf-8")
    assert output.stat().st_mode & 0o777 == 0o600
    assert "private-" not in report
    assert "data:image" not in report
    assert report.count("[REDACTED]") >= 4
    assert "event=bridge.ready" in report


def test_debug_redaction_is_bounded_and_does_not_modify_safe_diagnostics() -> None:
    safe = "event=turn.failed error_code=HERMES_FAILED duration_ms=120"

    assert redact_debug_text(safe) == safe
    assert len(redact_debug_text("x" * 2_000_000)) <= 1_048_600


def test_debug_report_cli_collects_only_safe_repository_and_host_metadata(
    tmp_path: Path,
    capsys: object,
) -> None:
    output = tmp_path / "operator-report.txt"

    assert debug_report.main(["--output", str(output)]) == 0

    report = output.read_text(encoding="utf-8")
    assert "git rev-parse HEAD" in report
    assert "python3.12" in report
    assert str(output) in capsys.readouterr().out  # type: ignore[attr-defined]
    assert "HERMES_API_KEY" not in report


def test_debug_report_refuses_overwrite_symlink_and_unbounded_log_inputs(tmp_path: Path) -> None:
    existing = tmp_path / "existing.txt"
    existing.write_text("owned", encoding="utf-8")
    linked = tmp_path / "linked.txt"
    linked.symlink_to(existing)
    oversized = tmp_path / "oversized.log"
    oversized.write_bytes(b"x" * (1_048_576 + 1))

    for output in (existing, linked):
        with pytest.raises(ValueError, match="new file"):
            create_debug_report(output, project_root=ROOT)

    with pytest.raises(ValueError, match="at most 10"):
        create_debug_report(
            tmp_path / "too-many.txt",
            log_paths=tuple(tmp_path / f"{index}.log" for index in range(11)),
            project_root=ROOT,
        )
    with pytest.raises(ValueError, match="no larger than 1 MiB"):
        create_debug_report(
            tmp_path / "oversized-report.txt",
            log_paths=(oversized,),
            project_root=ROOT,
            repository_summary="safe",
            host_summary="safe",
        )
