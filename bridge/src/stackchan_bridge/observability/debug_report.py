"""Create a bounded, credential-redacted local support report."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from stackchan_bridge.doctor import inspect_host

_MAX_TEXT_BYTES = 1_048_576
_MAX_LOG_FILES = 10
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)(Authorization\s*:\s*Bearer\s+)[^\s]+"), r"\1[REDACTED]"),
    (
        re.compile(
            r"(?im)\b((?:HERMES_API_KEY|STACKCHAN_DEVICE_TOKEN|STACKCHAN_(?:STT|TTS)_API_KEY)\s*=\s*)[^\s]+"
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r'(?i)("(?:api[_-]?key|device[_-]?token|token|password|wifi[_-]?password)"\s*:\s*")[^"]*(")'
        ),
        r"\1[REDACTED]\2",
    ),
    (
        re.compile(
            r"(?im)\b((?:api[_-]?key|device[_-]?token|token|password|wifi[_-]?password)\s*:\s*)[^\s]+"
        ),
        r"\1[REDACTED]",
    ),
    (re.compile(r"(?i)data:image/[a-z0-9.+-]+;base64,[a-z0-9+/=]+"), "[REDACTED]"),
)


def redact_debug_text(text: str) -> str:
    """Redact common credential/media forms and cap one input section."""

    bounded = text[:_MAX_TEXT_BYTES]
    if len(text) > _MAX_TEXT_BYTES:
        bounded += "\n[TRUNCATED]"
    for pattern, replacement in _REDACTIONS:
        bounded = pattern.sub(replacement, bounded)
    return bounded


def create_debug_report(
    output: Path,
    *,
    log_paths: tuple[Path, ...] = (),
    project_root: Path,
    repository_summary: str | None = None,
    host_summary: str | None = None,
) -> Path:
    """Write a new mode-0600 report without reading config or environment values."""

    if len(log_paths) > _MAX_LOG_FILES:
        raise ValueError("at most 10 log files may be included")
    if not output.parent.is_dir() or output.is_symlink() or output.exists():
        raise ValueError("debug report output must be a new file in an existing directory")
    repository = repository_summary or _repository_summary(project_root)
    host = host_summary or _host_summary()
    sections = [
        "# StackChan Hermes debug report",
        f"created_at={datetime.now(UTC).isoformat()}",
        "",
        "## repository",
        redact_debug_text(repository),
        "",
        "## host prerequisites",
        redact_debug_text(host),
    ]
    for path in log_paths:
        sections.extend(("", f"## log: {path.name}", redact_debug_text(_read_log(path))))
    payload = ("\n".join(sections) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(output, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as report_file:
            report_file.write(payload)
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return output


def _read_log(path: Path) -> str:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_TEXT_BYTES:
            raise ValueError("debug log must be a regular text file no larger than 1 MiB")
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise ValueError("debug log is unavailable") from error


def _repository_summary(project_root: Path) -> str:
    commands = (("git", "rev-parse", "HEAD"), ("git", "status", "--short"))
    results: list[str] = []
    for command in commands:
        try:
            result = subprocess.run(
                command,
                cwd=project_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            results.append(f"{' '.join(command)}: unavailable")
            continue
        output = result.stdout if result.returncode == 0 else "unavailable"
        results.append(f"{' '.join(command)}:\n{output.strip()}")
    return "\n".join(results)


def _host_summary() -> str:
    return json.dumps(
        {check.name: check.as_dict() for check in inspect_host()},
        ensure_ascii=False,
        sort_keys=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="create-debug-report")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--log", action="append", default=[], type=Path)
    args = parser.parse_args(argv)
    project_root = Path(__file__).resolve().parents[4]
    created = create_debug_report(
        args.output,
        log_paths=tuple(args.log),
        project_root=project_root,
    )
    print(created)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the shell wrapper
    raise SystemExit(main())
