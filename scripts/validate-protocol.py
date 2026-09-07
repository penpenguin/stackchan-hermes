#!/usr/bin/env python3
"""Validate protocol schemas and their checked-in examples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import FormatChecker
from jsonschema.validators import validator_for
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_DIR = ROOT / "protocol"
EXAMPLES_DIR = PROTOCOL_DIR / "examples"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return value


def _load_schemas() -> tuple[dict[str, Any], Registry[Any]]:
    schemas_by_id: dict[str, Any] = {}
    resources: list[tuple[str, Resource[Any]]] = []
    for path in sorted(PROTOCOL_DIR.glob("*.schema.json")):
        schema = _load_json(path)
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str) or not schema_id:
            raise ValueError(f"{path}: schema must define a non-empty $id")
        validator_for(schema).check_schema(schema)
        schemas_by_id[schema_id] = schema
        resources.append((schema_id, Resource.from_contents(schema)))
    return schemas_by_id, Registry().with_resources(resources)


def main() -> int:
    schemas_by_id, registry = _load_schemas()
    manifest = _load_json(EXAMPLES_DIR / "manifest.json")
    entries = manifest.get("examples")
    if not isinstance(entries, list):
        raise ValueError("protocol example manifest must contain an examples array")

    valid_count = 0
    invalid_count = 0
    failures: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            failures.append("manifest entry is not an object")
            continue
        example_path = EXAMPLES_DIR / str(entry.get("path", ""))
        schema_id = str(entry.get("schema", ""))
        expected_valid = entry.get("valid") is True
        schema = schemas_by_id.get(schema_id)
        if schema is None:
            failures.append(f"{example_path.name}: unknown schema {schema_id!r}")
            continue
        instance = _load_json(example_path)
        validator_class = validator_for(schema)
        errors = list(
            validator_class(
                schema,
                registry=registry,
                format_checker=FormatChecker(),
            ).iter_errors(instance)
        )
        if expected_valid and errors:
            failures.append(f"{example_path.name}: {errors[0].message}")
        elif not expected_valid and not errors:
            failures.append(f"{example_path.name}: unexpectedly passed validation")
        elif expected_valid:
            valid_count += 1
        else:
            invalid_count += 1

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print(f"Protocol validation passed: {valid_count} valid examples")
    invalid_label = "example" if invalid_count == 1 else "examples"
    print(f"Protocol validation passed: {invalid_count} expected invalid {invalid_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
