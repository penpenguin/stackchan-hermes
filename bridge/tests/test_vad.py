from __future__ import annotations

import numpy as np
from stackchan_bridge.audio.vad import RmsVad, RmsVadConfig, VadEndReason, VadUtterance


def constant_pcm(amplitude: int, *, frame_ms: int = 20) -> bytes:
    return np.full(16_000 * frame_ms // 1_000, amplitude, dtype="<i2").tobytes()


def feed(vad: RmsVad, amplitude: int, duration_ms: int) -> list[VadUtterance]:
    results: list[VadUtterance] = []
    for _ in range(duration_ms // vad.config.frame_ms):
        result = vad.process(constant_pcm(amplitude, frame_ms=vad.config.frame_ms))
        if result is not None:
            results.append(result)
    return results


def test_rms_vad_keeps_short_pauses_and_ends_on_long_silence_with_preroll() -> None:
    vad = RmsVad(
        RmsVadConfig(
            frame_ms=20,
            start_speech_ms=60,
            end_silence_ms=650,
            minimum_speech_ms=240,
            preroll_ms=360,
            maximum_recording_ms=15_000,
            start_threshold=1_000,
            end_threshold=500,
        )
    )

    assert feed(vad, 0, 400) == []
    assert feed(vad, 4_000, 300) == []
    assert feed(vad, 0, 200) == []
    assert feed(vad, 4_000, 300) == []
    completed = feed(vad, 0, 660)

    assert len(completed) == 1
    utterance = completed[0]
    assert utterance.reason is VadEndReason.SILENCE
    assert utterance.accepted is True
    assert utterance.speech_ms >= 600
    assert utterance.duration_ms >= 1_160
    assert len(utterance.pcm) == utterance.duration_ms * 16_000 * 2 // 1_000


def test_rms_vad_marks_a_short_sound_as_not_accepted() -> None:
    vad = RmsVad(
        RmsVadConfig(
            start_speech_ms=60,
            end_silence_ms=200,
            minimum_speech_ms=240,
            start_threshold=1_000,
            end_threshold=500,
        )
    )

    assert feed(vad, 4_000, 100) == []
    completed = feed(vad, 0, 200)

    assert len(completed) == 1
    assert completed[0].reason is VadEndReason.TOO_SHORT
    assert completed[0].accepted is False
    assert completed[0].speech_ms == 100


def test_rms_vad_ends_an_unbroken_utterance_at_the_maximum_duration() -> None:
    vad = RmsVad(
        RmsVadConfig(
            start_speech_ms=60,
            end_silence_ms=650,
            minimum_speech_ms=240,
            preroll_ms=100,
            maximum_recording_ms=400,
            start_threshold=1_000,
            end_threshold=500,
        )
    )

    assert feed(vad, 0, 100) == []
    completed = feed(vad, 4_000, 400)

    assert len(completed) == 1
    assert completed[0].reason is VadEndReason.MAX_DURATION
    assert completed[0].accepted is True
    assert completed[0].duration_ms == 400


def test_rms_vad_finish_accepts_active_speech_without_waiting_for_end_silence() -> None:
    vad = RmsVad(
        RmsVadConfig(
            start_speech_ms=60,
            end_silence_ms=650,
            minimum_speech_ms=240,
            preroll_ms=100,
            start_threshold=1_000,
            end_threshold=500,
        )
    )

    assert feed(vad, 0, 100) == []
    assert feed(vad, 4_000, 300) == []
    utterance = vad.finish()

    assert utterance is not None
    assert utterance.accepted is True
    assert utterance.speech_ms == 300
    assert utterance.duration_ms == 400


def test_rms_vad_finish_rejects_noise_without_detected_speech() -> None:
    vad = RmsVad(RmsVadConfig())

    assert feed(vad, 100, 500) == []
    assert vad.finish() is None
