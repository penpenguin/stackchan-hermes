"""In-memory WAV serialization for normalized PCM adapters."""

from __future__ import annotations

from io import BytesIO
from wave import open as open_wave

from stackchan_bridge.audio.types import PcmAudio


def pcm_to_wav(audio: PcmAudio) -> bytes:
    buffer = BytesIO()
    with open_wave(buffer, "wb") as wav_file:
        wav_file.setnchannels(audio.channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(audio.sample_rate)
        wav_file.writeframes(audio.pcm)
    return buffer.getvalue()
