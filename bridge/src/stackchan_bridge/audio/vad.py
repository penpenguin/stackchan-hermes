"""Deterministic frame-based RMS voice activity detection."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from math import sqrt

import numpy as np


class VadEndReason(StrEnum):
    SILENCE = "silence"
    MAX_DURATION = "max_duration"
    TOO_SHORT = "too_short"


@dataclass(frozen=True, slots=True)
class RmsVadConfig:
    sample_rate: int = 16_000
    frame_ms: int = 20
    start_speech_ms: int = 60
    end_silence_ms: int = 650
    minimum_speech_ms: int = 240
    preroll_ms: int = 360
    maximum_recording_ms: int = 15_000
    start_threshold: float = 1_000
    end_threshold: float = 500
    initial_noise_floor: float = 50
    noise_floor_alpha: float = 0.05
    noise_start_ratio: float = 3.0
    noise_end_ratio: float = 1.8

    def __post_init__(self) -> None:
        if self.sample_rate != 16_000:
            raise ValueError("RMS VAD requires 16000 Hz PCM")
        if self.frame_ms <= 0 or 1_000 % self.frame_ms != 0:
            raise ValueError("VAD frame duration must divide one second")
        for value in (
            self.start_speech_ms,
            self.end_silence_ms,
            self.minimum_speech_ms,
            self.maximum_recording_ms,
        ):
            if value <= 0:
                raise ValueError("VAD durations must be positive")
        if self.preroll_ms < 0:
            raise ValueError("VAD preroll cannot be negative")
        if self.end_threshold >= self.start_threshold:
            raise ValueError("VAD end threshold must be below start threshold")
        if not 0 < self.noise_floor_alpha <= 1:
            raise ValueError("noise floor alpha must be in (0, 1]")

    @property
    def frame_bytes(self) -> int:
        return self.sample_rate * self.frame_ms // 1_000 * 2


@dataclass(frozen=True, slots=True)
class VadUtterance:
    pcm: bytes
    reason: VadEndReason
    accepted: bool
    speech_ms: int
    duration_ms: int


class RmsVad:
    """Segment signed-16 mono PCM without using wall-clock scheduling."""

    def __init__(self, config: RmsVadConfig) -> None:
        self.config = config
        self._preroll_frames = config.preroll_ms // config.frame_ms
        start_frames = (config.start_speech_ms + config.frame_ms - 1) // config.frame_ms
        self._preroll: deque[bytes] = deque(maxlen=self._preroll_frames + start_frames)
        self._recording: list[bytes] = []
        self._active = False
        self._start_run_ms = 0
        self._silence_ms = 0
        self._speech_ms = 0
        self._noise_floor = config.initial_noise_floor

    @property
    def active(self) -> bool:
        return self._active

    @property
    def noise_floor(self) -> float:
        return self._noise_floor

    def process(self, pcm_frame: bytes) -> VadUtterance | None:
        if len(pcm_frame) != self.config.frame_bytes:
            raise ValueError(f"PCM frame must contain exactly {self.config.frame_bytes} bytes")
        rms = _pcm_rms(pcm_frame)
        start_level = max(
            self.config.start_threshold,
            self._noise_floor * self.config.noise_start_ratio,
        )
        end_level = max(
            self.config.end_threshold,
            self._noise_floor * self.config.noise_end_ratio,
        )

        if not self._active:
            self._preroll.append(pcm_frame)
            if rms >= start_level:
                self._start_run_ms += self.config.frame_ms
            else:
                self._start_run_ms = 0
                self._update_noise_floor(rms)
            if self._start_run_ms >= self.config.start_speech_ms:
                self._active = True
                self._recording = list(self._preroll)
                self._preroll.clear()
                self._speech_ms = self._start_run_ms
                self._silence_ms = 0
            return None

        self._recording.append(pcm_frame)
        if rms >= end_level:
            self._speech_ms += self.config.frame_ms
            self._silence_ms = 0
        else:
            self._silence_ms += self.config.frame_ms
        duration_ms = len(self._recording) * self.config.frame_ms
        if duration_ms >= self.config.maximum_recording_ms:
            return self._complete(VadEndReason.MAX_DURATION)
        if self._silence_ms >= self.config.end_silence_ms:
            return self._complete(VadEndReason.SILENCE)
        return None

    def finish(self) -> VadUtterance | None:
        """Finish an externally ended input stream without inventing speech."""

        if not self._active:
            self._preroll.clear()
            self._start_run_ms = 0
            return None
        return self._complete(VadEndReason.SILENCE)

    def _complete(self, reason: VadEndReason) -> VadUtterance:
        accepted = self._speech_ms >= self.config.minimum_speech_ms
        selected_reason = reason if accepted else VadEndReason.TOO_SHORT
        recording = self._recording
        utterance = VadUtterance(
            pcm=b"".join(recording),
            reason=selected_reason,
            accepted=accepted,
            speech_ms=self._speech_ms,
            duration_ms=len(recording) * self.config.frame_ms,
        )
        trailing_frames = list(recording)[-self._preroll_frames :] if self._preroll_frames else []
        self._preroll.clear()
        self._preroll.extend(trailing_frames)
        self._recording = []
        self._active = False
        self._start_run_ms = 0
        self._silence_ms = 0
        self._speech_ms = 0
        return utterance

    def _update_noise_floor(self, rms: float) -> None:
        alpha = self.config.noise_floor_alpha
        self._noise_floor = (1 - alpha) * self._noise_floor + alpha * rms


def _pcm_rms(pcm: bytes) -> float:
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    return sqrt(float(np.mean(np.square(samples))))
