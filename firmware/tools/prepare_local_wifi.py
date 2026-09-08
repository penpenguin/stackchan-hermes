#!/usr/bin/env python3
"""Apply the reviewed local Wi-Fi patch without changing the managed component cache."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from hashlib import sha256
from pathlib import Path


def _relative(name: str) -> Path:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Invalid local Wi-Fi patch path")
    return path


def prepare(firmware: Path, output: Path) -> None:
    manifest = json.loads((firmware / "patches/esp-wifi-connect.json").read_text())
    patch = firmware / "patches/esp-wifi-connect.patch"
    if sha256(patch.read_bytes()).hexdigest() != manifest["patch_sha256"]:
        raise ValueError("Local Wi-Fi patch hash differs")
    component = firmware / _relative(manifest["component"])
    if output.resolve().is_relative_to(component.resolve()):
        raise ValueError("Local Wi-Fi output cannot overwrite the source cache")
    with tempfile.TemporaryDirectory(prefix="stackchan-wifi-patch-") as temporary:
        staged = Path(temporary)
        for record in manifest["files"]:
            relative = _relative(record["source"])
            data = (component / relative).read_bytes()
            if sha256(data).hexdigest() != record["source_sha256"]:
                raise ValueError(f"Local Wi-Fi source hash differs: {relative}")
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        subprocess.run(
            ["git", "apply", "--check", str(patch.resolve())],
            cwd=staged,
            check=True,
            capture_output=True,
            env={**os.environ, "GIT_CEILING_DIRECTORIES": str(staged.parent)},
        )
        subprocess.run(
            ["git", "apply", str(patch.resolve())],
            cwd=staged,
            check=True,
            capture_output=True,
            env={**os.environ, "GIT_CEILING_DIRECTORIES": str(staged.parent)},
        )
        outputs: dict[Path, bytes] = {}
        for record in manifest["files"]:
            data = (staged / record["source"]).read_bytes()
            if sha256(data).hexdigest() != record["output_sha256"]:
                raise ValueError("Local Wi-Fi patched output hash differs")
            outputs[_relative(record["output"])] = data
        for relative, data in outputs.items():
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or target.read_bytes() != data:
                target.write_bytes(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare(Path(__file__).resolve().parents[1], args.output)
