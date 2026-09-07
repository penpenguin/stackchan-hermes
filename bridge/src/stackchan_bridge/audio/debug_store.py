"""Explicit opt-in, short-lived storage for decoded microphone diagnostics."""

from __future__ import annotations

import os
import re
from pathlib import Path
from time import time
from uuid import UUID

from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.audio.wav import pcm_to_wav

_OWNED_WAV_NAME = re.compile(r"^[0-9a-f]{32}\.wav$")


class DebugAudioStore:
    """Persist private WAV diagnostics only when the operator opts in."""

    def __init__(self, *, directory: Path, ttl_seconds: int, enabled: bool) -> None:
        if ttl_seconds <= 0:
            raise ValueError("debug audio TTL must be positive")
        self._directory = directory
        self._ttl_seconds = ttl_seconds
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def directory(self) -> Path:
        return self._directory

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    def save(self, turn_id: UUID, audio: PcmAudio) -> Path | None:
        if not self._enabled:
            return None
        self._directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self._directory / f"{turn_id.hex}.wav"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(pcm_to_wav(audio))
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return path

    def purge_expired(self, *, now: float | None = None) -> int:
        if not self._enabled or not self._directory.is_dir():
            return 0
        cutoff = (time() if now is None else now) - self._ttl_seconds
        purged = 0
        for path in self._directory.iterdir():
            if not _OWNED_WAV_NAME.fullmatch(path.name) or path.is_symlink():
                continue
            try:
                if path.is_file() and path.stat().st_mtime <= cutoff:
                    path.unlink()
                    purged += 1
            except FileNotFoundError:
                continue
        return purged
