from __future__ import annotations

from math import pi

import numpy as np
import pytest
from stackchan_bridge.audio.codec import AudioCodecError, OpusCodec, OpusCodecConfig
from stackchan_bridge.protocol.models import MAX_AUDIO_PACKET_BYTES


def sine_pcm(frame_ms: int, *, frequency_hz: float = 440.0) -> bytes:
    sample_count = 16_000 * frame_ms // 1_000
    times = np.arange(sample_count, dtype=np.float64) / 16_000
    samples = np.sin(2 * pi * frequency_hz * times) * 12_000
    return samples.astype("<i2").tobytes()


@pytest.mark.parametrize("frame_ms", [20, 40, 60])
def test_opus_codec_round_trips_each_protocol_frame_size(frame_ms: int) -> None:
    codec = OpusCodec(OpusCodecConfig(frame_ms=frame_ms))
    pcm = sine_pcm(frame_ms)

    packet = codec.encode(pcm)
    decoded = codec.decode(packet)

    assert 0 < len(packet) <= MAX_AUDIO_PACKET_BYTES
    assert len(decoded) == len(pcm)
    assert np.frombuffer(decoded, dtype="<i2").std() > 100


def test_opus_codec_rejects_a_partial_pcm_frame() -> None:
    codec = OpusCodec(OpusCodecConfig(frame_ms=60))

    with pytest.raises(ValueError, match="PCM frame"):
        codec.encode(b"\x00\x00")


@pytest.mark.parametrize(
    "bad_packet",
    [b"bad", b"", b"x" * (MAX_AUDIO_PACKET_BYTES + 1)],
    ids=["malformed", "empty", "oversized"],
)
def test_opus_codec_recovers_with_a_fresh_decoder_after_a_bad_packet(bad_packet: bytes) -> None:
    codec = OpusCodec(OpusCodecConfig(frame_ms=60))
    valid_packet = codec.encode(sine_pcm(60))

    with pytest.raises(AudioCodecError, match="decode"):
        codec.decode(bad_packet)

    assert codec.consecutive_decode_errors == 1
    assert len(codec.decode(valid_packet)) == len(sine_pcm(60))
    assert codec.consecutive_decode_errors == 0
