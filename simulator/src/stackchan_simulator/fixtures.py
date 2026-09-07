"""Runtime-only synthetic media fixtures; no user media is tracked."""

from __future__ import annotations

import subprocess


def generate_synthetic_jpeg() -> bytes:
    """Generate a deterministic 320x240 color frame through the required ffmpeg tool."""

    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:d=0.04",
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "pipe:1",
        ],
        check=False,
        capture_output=True,
        timeout=10,
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"ffmpeg failed to generate synthetic JPEG: {detail}")
    return result.stdout
