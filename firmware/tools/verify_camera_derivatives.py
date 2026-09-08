"""Verify reviewed camera derivatives and their actual compilation inputs."""

from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path


def verify_camera_derivatives(
    root: Path, manifest: Path, commands: list[dict[str, str]] | None = None
) -> None:
    root = root.resolve()
    files = json.loads(manifest.read_text())["files"]
    if not files:
        raise ValueError("Camera derivative manifest is empty")
    compiled = [Path(command["file"]).resolve() for command in commands or []]
    for entry in files:
        paths = {}
        for side in ("source", "derivative"):
            path = (root / entry[side]).resolve()
            if not path.is_relative_to(root):
                raise ValueError("Camera derivative path escapes the repository")
            if sha256(path.read_bytes()).hexdigest() != entry[side + "_sha256"]:
                raise ValueError(f"Camera {side} hash differs: {entry[side]}")
            paths[side] = path
        if commands is not None and (
            compiled.count(paths["derivative"]) != 1 or paths["source"] in compiled
        ):
            raise ValueError(f"Camera compilation inputs differ: {entry['derivative']}")


if __name__ == "__main__":
    repository = Path(__file__).resolve().parents[2]
    try:
        verify_camera_derivatives(repository, repository / "firmware/patches/camera-derivatives.json")
    except (OSError, ValueError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error
