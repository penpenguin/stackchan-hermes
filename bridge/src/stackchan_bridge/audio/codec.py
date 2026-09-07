"""Bounded Opus codec wrapper for protocol audio frames."""

from __future__ import annotations

from dataclasses import dataclass

import opuslib_next  # type: ignore[import-untyped]
from opuslib_next.exceptions import OpusError  # type: ignore[import-untyped]

from stackchan_bridge.protocol.models import MAX_AUDIO_PACKET_BYTES


class AudioCodecError(RuntimeError):
    """libopus could not encode or decode one isolated frame."""


@dataclass(frozen=True, slots=True)
class OpusCodecConfig:
    sample_rate: int = 16_000
    channels: int = 1
    frame_ms: int = 60

    def __post_init__(self) -> None:
        if self.sample_rate != 16_000:
            raise ValueError("protocol sample rate must be 16000 Hz")
        if self.channels != 1:
            raise ValueError("protocol audio must be mono")
        if self.frame_ms not in {20, 40, 60}:
            raise ValueError("protocol frame duration must be 20, 40, or 60 ms")

    @property
    def frame_samples(self) -> int:
        return self.sample_rate * self.frame_ms // 1_000

    @property
    def pcm_bytes(self) -> int:
        return self.frame_samples * self.channels * 2


class OpusCodec:
    """One encoder/decoder pair with exact frame and packet bounds."""

    def __init__(self, config: OpusCodecConfig) -> None:
        self.config = config
        self._encoder = opuslib_next.Encoder(
            config.sample_rate,
            config.channels,
            opuslib_next.APPLICATION_VOIP,
        )
        self._decoder = self._new_decoder()
        self._consecutive_decode_errors = 0

    @property
    def consecutive_decode_errors(self) -> int:
        return self._consecutive_decode_errors

    def encode(self, pcm: bytes) -> bytes:
        if len(pcm) != self.config.pcm_bytes:
            raise ValueError(f"PCM frame must contain exactly {self.config.pcm_bytes} bytes")
        try:
            packet = self._encoder.encode(pcm, self.config.frame_samples)
        except OpusError as error:
            raise AudioCodecError("Opus encode failed") from error
        if not isinstance(packet, bytes) or not packet or len(packet) > MAX_AUDIO_PACKET_BYTES:
            raise AudioCodecError("Opus encoder returned an invalid packet size")
        return packet

    def decode(self, packet: bytes) -> bytes:
        if not packet or len(packet) > MAX_AUDIO_PACKET_BYTES:
            self._recover_decoder()
            raise AudioCodecError("Opus decode packet size is outside the protocol limit")
        try:
            decoded = self._decoder.decode(packet, self.config.frame_samples)
        except OpusError as error:
            self._recover_decoder()
            raise AudioCodecError("Opus decode failed") from error
        if not isinstance(decoded, bytes) or len(decoded) != self.config.pcm_bytes:
            self._recover_decoder()
            raise AudioCodecError("Opus decoder returned an invalid PCM frame")
        self._consecutive_decode_errors = 0
        return decoded

    def _new_decoder(self) -> opuslib_next.Decoder:
        return opuslib_next.Decoder(self.config.sample_rate, self.config.channels)

    def _recover_decoder(self) -> None:
        self._consecutive_decode_errors += 1
        self._decoder = self._new_decoder()
