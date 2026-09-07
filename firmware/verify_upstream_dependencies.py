#!/usr/bin/env python3
"""Verify fetched Firmware dependencies against the reviewed upstream lock."""

from __future__ import annotations

import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any


class DependencyVerificationError(RuntimeError):
    """Raised when a fetched dependency differs from the reviewed lock."""


def _git(repository: Path, *arguments: str, text: bool) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=text,
    )
    if result.returncode != 0:
        raise DependencyVerificationError(f"git verification failed for {repository.name}")
    return result.stdout


def _dependency_path(firmware_root: Path, relative_path: str) -> Path:
    root = firmware_root.resolve()
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise DependencyVerificationError(f"dependency path escapes firmware root: {relative_path}")
    if not candidate.is_dir():
        raise DependencyVerificationError(f"dependency is missing: {relative_path}")
    return candidate


def _load_dependencies(lock_path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        dependencies = payload["fetched_repositories"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DependencyVerificationError("upstream dependency lock is invalid") from exc
    if not isinstance(dependencies, list) or not dependencies:
        raise DependencyVerificationError("upstream dependency lock has no repositories")
    return dependencies


def verify_dependencies(firmware_root: Path) -> list[str]:
    """Return verified dependency paths or raise on the first mismatch."""

    verified: list[str] = []
    for dependency in _load_dependencies(firmware_root / "upstream-lock.json"):
        relative_path = dependency.get("path")
        expected_commit = dependency.get("commit")
        if not isinstance(relative_path, str) or not isinstance(expected_commit, str):
            raise DependencyVerificationError("upstream dependency entry is invalid")

        repository = _dependency_path(firmware_root, relative_path)
        actual_commit = _git(repository, "rev-parse", "HEAD", text=True)
        assert isinstance(actual_commit, str)
        if actual_commit.strip() != expected_commit:
            raise DependencyVerificationError(f"commit mismatch: {relative_path}")

        diff = _git(
            repository,
            "diff",
            "HEAD",
            "--binary",
            "--no-ext-diff",
            "--no-textconv",
            text=False,
        )
        assert isinstance(diff, bytes)
        patch_path = dependency.get("patch")
        expected_diff_sha256 = dependency.get("patched_diff_sha256")
        if patch_path is None and expected_diff_sha256 is None:
            if diff:
                raise DependencyVerificationError(f"unreviewed changes: {relative_path}")
        elif isinstance(patch_path, str) and isinstance(expected_diff_sha256, str):
            reviewed_patch = (firmware_root / patch_path).read_bytes()
            if sha256(reviewed_patch).hexdigest() != expected_diff_sha256:
                raise DependencyVerificationError(f"reviewed patch mismatch: {relative_path}")
            if sha256(diff).hexdigest() != expected_diff_sha256:
                raise DependencyVerificationError(f"patch diff mismatch: {relative_path}")
        else:
            raise DependencyVerificationError(f"incomplete patch lock: {relative_path}")

        verified.append(relative_path)
    return verified


def main() -> int:
    firmware_root = Path(__file__).resolve().parent
    try:
        verified = verify_dependencies(firmware_root)
    except (DependencyVerificationError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Verified {len(verified)} locked Firmware dependencies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
