"""Provider-neutral normalized PCM value objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PcmAudio:
    """Signed 16-bit little-endian mono PCM normalized for Bridge adapters."""

    pcm: bytes
    sample_rate: int = 16_000
    channels: int = 1

    def __post_init__(self) -> None:
        if self.sample_rate != 16_000:
            raise ValueError("normalized PCM sample rate must be 16000 Hz")
        if self.channels != 1:
            raise ValueError("normalized PCM must be mono")
        if len(self.pcm) % 2:
            raise ValueError("signed 16-bit PCM must contain complete samples")

    @property
    def duration_seconds(self) -> float:
        return len(self.pcm) / (self.sample_rate * self.channels * 2)
