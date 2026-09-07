from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

import pytest
from stackchan_bridge.audio.debug_store import DebugAudioStore
from stackchan_bridge.audio.types import PcmAudio

TURN_ID = UUID("168b58ca-7c31-4744-b445-d2f20c9bdde0")


def test_debug_audio_store_is_inert_when_not_explicitly_enabled(tmp_path: Path) -> None:
    directory = tmp_path / "debug-audio"
    store = DebugAudioStore(
        directory=directory,
        ttl_seconds=600,
        enabled=False,
    )

    assert store.save(TURN_ID, PcmAudio(pcm=b"\x00\x00" * 160)) is None
    assert store.purge_expired(now=1_000) == 0
    assert directory.exists() is False


def test_debug_audio_store_writes_private_wav_and_purges_only_expired_owned_names(
    tmp_path: Path,
) -> None:
    store = DebugAudioStore(
        directory=tmp_path,
        ttl_seconds=600,
        enabled=True,
    )
    saved = store.save(TURN_ID, PcmAudio(pcm=b"\x01\x00" * 160))
    assert saved is not None
    assert saved.name == f"{TURN_ID.hex}.wav"
    assert saved.read_bytes().startswith(b"RIFF")
    assert saved.stat().st_mode & 0o777 == 0o600

    unknown = tmp_path / "keep.wav"
    unknown.write_bytes(b"user-owned")
    active = tmp_path / "00000000000000000000000000000001.wav"
    active.write_bytes(b"RIFF-active")
    symlink = tmp_path / "00000000000000000000000000000002.wav"
    symlink.symlink_to(unknown)
    os.utime(saved, (100, 100))
    os.utime(unknown, (100, 100))
    os.utime(active, (900, 900))

    assert store.purge_expired(now=1_000) == 1
    assert saved.exists() is False
    assert unknown.read_bytes() == b"user-owned"
    assert active.exists() is True
    assert symlink.is_symlink() is True


def test_debug_audio_store_rejects_invalid_ttl_and_never_overwrites_a_turn(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="TTL"):
        DebugAudioStore(directory=tmp_path, ttl_seconds=0, enabled=True)

    store = DebugAudioStore(directory=tmp_path, ttl_seconds=60, enabled=True)
    first = store.save(TURN_ID, PcmAudio(pcm=b"\x01\x00" * 10))
    assert first is not None
    original = first.read_bytes()

    with pytest.raises(FileExistsError):
        store.save(TURN_ID, PcmAudio(pcm=b"\x02\x00" * 10))

    assert first.read_bytes() == original
