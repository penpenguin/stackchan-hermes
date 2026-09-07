"""Normalize provider audio to bounded 16 kHz mono signed-16 PCM."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from stackchan_bridge.audio.types import PcmAudio


def normalize_audio(
    samples: NDArray[np.float64],
    *,
    sample_rate: int,
    gain: float,
    leading_silence_ms: int = 0,
    trailing_silence_ms: int = 0,
) -> PcmAudio:
    """Downmix, remove DC, resample, gain, and pad floating-point provider audio."""

    values: NDArray[np.float64] = np.asarray(samples, dtype=np.float64)
    if values.ndim not in {1, 2} or values.size == 0:
        raise ValueError("provider audio must contain one- or two-dimensional samples")
    if not np.isfinite(values).all():
        raise ValueError("provider audio contains non-finite samples")
    if sample_rate <= 0:
        raise ValueError("provider sample rate must be positive")
    if not 0 <= gain <= 2:
        raise ValueError("audio gain must be between zero and two")
    if leading_silence_ms < 0 or trailing_silence_ms < 0:
        raise ValueError("audio silence padding cannot be negative")

    mono = values.mean(axis=1) if values.ndim == 2 else values.copy()
    mono -= mono.mean()
    resampled = _resample(mono, source_rate=sample_rate, target_rate=16_000)
    scaled = np.clip(resampled * gain, -1.0, 1.0)
    voice = np.rint(scaled * 32_767).astype("<i2")
    leading = np.zeros(16_000 * leading_silence_ms // 1_000, dtype="<i2")
    trailing = np.zeros(16_000 * trailing_silence_ms // 1_000, dtype="<i2")
    normalized = np.concatenate((leading, voice, trailing))
    return PcmAudio(pcm=normalized.tobytes())


def _resample(
    samples: NDArray[np.float64],
    *,
    source_rate: int,
    target_rate: int,
) -> NDArray[np.float64]:
    if source_rate == target_rate:
        return samples
    target_count = max(1, round(len(samples) * target_rate / source_rate))
    source_positions: NDArray[Any] = np.arange(len(samples), dtype=np.float64)
    target_positions = np.arange(target_count, dtype=np.float64) * source_rate / target_rate
    return np.interp(target_positions, source_positions, samples)
