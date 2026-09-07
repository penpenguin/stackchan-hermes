#!/usr/bin/env python3
"""Verify ESP-IDF managed components against the upstream dependency lock."""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

HashValidator = Callable[[Path, str], None]


class ManagedComponentVerificationError(RuntimeError):
    """Raised when a managed component differs from the reviewed lock."""


def _expected_components(lock_payload: object) -> dict[str, tuple[str, str]]:
    if not isinstance(lock_payload, dict):
        raise ManagedComponentVerificationError("managed dependency lock is invalid")
    dependencies = lock_payload.get("dependencies")
    if not isinstance(dependencies, dict) or not dependencies:
        raise ManagedComponentVerificationError("managed dependency lock has no dependencies")

    expected: dict[str, tuple[str, str]] = {}
    for name, dependency in dependencies.items():
        if not isinstance(name, str) or not isinstance(dependency, dict):
            raise ManagedComponentVerificationError("managed dependency entry is invalid")
        source = dependency.get("source")
        if not isinstance(source, dict):
            raise ManagedComponentVerificationError(f"managed dependency source is invalid: {name}")
        source_type = source.get("type")
        if source_type == "idf":
            continue
        if source_type != "service":
            raise ManagedComponentVerificationError(f"unsupported dependency source: {name}")

        expected_hash = dependency.get("component_hash")
        if (
            not isinstance(expected_hash, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None
        ):
            raise ManagedComponentVerificationError(f"managed dependency hash is invalid: {name}")
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name) is None:
            raise ManagedComponentVerificationError(f"managed dependency name is unsafe: {name}")

        directory_name = name.replace("/", "__")
        if directory_name in expected:
            raise ManagedComponentVerificationError(f"managed dependency path collision: {name}")
        expected[directory_name] = (name, expected_hash)

    if not expected:
        raise ManagedComponentVerificationError("managed dependency lock has no service components")
    return expected


def verify_managed_components(
    firmware_root: Path,
    lock_payload: object,
    validate_hash: HashValidator,
) -> list[str]:
    """Return verified component names or raise on the first mismatch."""

    expected = _expected_components(lock_payload)
    managed_root = firmware_root / "managed_components"
    if not managed_root.is_dir():
        raise ManagedComponentVerificationError("managed_components is missing")

    actual_paths = {path.name: path for path in managed_root.iterdir() if path.is_dir()}
    if set(actual_paths) != set(expected):
        missing = sorted(set(expected) - set(actual_paths))
        unexpected = sorted(set(actual_paths) - set(expected))
        raise ManagedComponentVerificationError(
            f"managed component directory mismatch: missing={missing}, unexpected={unexpected}"
        )

    verified: list[str] = []
    for directory_name in sorted(expected):
        component_name, expected_hash = expected[directory_name]
        component_path = actual_paths[directory_name]
        if component_path.is_symlink():
            raise ManagedComponentVerificationError(
                f"managed component must not be a symlink: {component_name}"
            )

        try:
            recorded_hash = (component_path / ".component_hash").read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ManagedComponentVerificationError(
                f"managed component hash file is missing: {component_name}"
            ) from exc
        if recorded_hash != expected_hash:
            raise ManagedComponentVerificationError(
                f"managed component lock hash mismatch: {component_name}"
            )

        try:
            validate_hash(component_path, expected_hash)
        except Exception as exc:
            raise ManagedComponentVerificationError(
                f"managed component content mismatch: {component_name}"
            ) from exc
        verified.append(component_name)

    return verified


def _load_lock(path: Path) -> Any:
    try:
        import yaml
    except ImportError as exc:
        raise ManagedComponentVerificationError(
            "ESP-IDF Python environment is required for managed component verification"
        ) from exc
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ManagedComponentVerificationError("managed dependency lock is invalid") from exc


def _load_hash_validator() -> HashValidator:
    try:
        from idf_component_tools.hash_tools.validate import validate_hash_eq_hashdir
    except ImportError as exc:
        raise ManagedComponentVerificationError(
            "ESP-IDF component tools are required for managed component verification"
        ) from exc
    return validate_hash_eq_hashdir


def main() -> int:
    firmware_root = Path(__file__).resolve().parent
    try:
        verified = verify_managed_components(
            firmware_root,
            _load_lock(firmware_root / "dependencies.lock"),
            _load_hash_validator(),
        )
    except ManagedComponentVerificationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Verified {len(verified)} locked ESP-IDF managed components.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
