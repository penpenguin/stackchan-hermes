"""Provider-neutral TTS contract and deterministic mock."""

from __future__ import annotations

import builtins
import json
from asyncio import timeout
from dataclasses import dataclass, field
from io import BytesIO
from math import pi
from typing import Protocol

import httpx
import numpy as np
import soundfile  # type: ignore[import-untyped]
from pydantic import JsonValue, SecretStr

from stackchan_bridge.audio.normalize import normalize_audio
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.tts.errors import TtsProviderError, TtsTimeoutError

_MAX_VOICEVOX_QUERY_BYTES = 262_144
_MAX_WAV_RESPONSE_BYTES = 16_777_216
_MAX_AUDIO_DURATION_MS = 120_000
_MAX_DECODED_SAMPLE_VALUES = _MAX_WAV_RESPONSE_BYTES // 2


@dataclass(frozen=True, slots=True)
class TtsResult:
    audio: PcmAudio
    provider_metadata: dict[str, JsonValue]


class TtsAdapter(Protocol):
    async def synthesize(self, text: str) -> TtsResult: ...


@dataclass(frozen=True, slots=True)
class MockTtsAdapter:
    milliseconds_per_character: int = 80
    minimum_duration_ms: int = 200
    maximum_duration_ms: int = 5_000
    frequency_hz: float = 440

    def __post_init__(self) -> None:
        if self.milliseconds_per_character <= 0 or self.minimum_duration_ms <= 0:
            raise ValueError("Mock TTS durations must be positive")
        if self.maximum_duration_ms < self.minimum_duration_ms:
            raise ValueError("Mock TTS maximum must cover its minimum")
        if self.frequency_hz <= 0:
            raise ValueError("Mock TTS frequency must be positive")

    async def synthesize(self, text: str) -> TtsResult:
        if not text.strip():
            raise ValueError("TTS text cannot be empty")
        duration_ms = min(
            self.maximum_duration_ms,
            max(self.minimum_duration_ms, len(text) * self.milliseconds_per_character),
        )
        sample_count = 16_000 * duration_ms // 1_000
        times = np.arange(sample_count, dtype=np.float64) / 16_000
        samples = np.sin(2 * pi * self.frequency_hz * times) * 8_000
        return TtsResult(
            audio=PcmAudio(pcm=samples.astype("<i2").tobytes()),
            provider_metadata={"provider": "mock"},
        )


@dataclass(slots=True)
class GenericHttpWavTtsAdapter:
    client: httpx.AsyncClient = field(repr=False)
    endpoint: str
    api_key: SecretStr | None = field(default=None, repr=False)
    gain: float = 0.65
    leading_silence_ms: int = 0
    trailing_silence_ms: int = 0

    async def synthesize(self, text: str) -> TtsResult:
        if not text.strip():
            raise ValueError("TTS text cannot be empty")
        return await _synthesize_http_wav(
            self.client,
            endpoint=self.endpoint,
            payload={"text": text},
            provider="http-wav",
            api_key=self.api_key,
            gain=self.gain,
            leading_silence_ms=self.leading_silence_ms,
            trailing_silence_ms=self.trailing_silence_ms,
        )


@dataclass(slots=True)
class OpenAICompatibleTtsAdapter:
    client: httpx.AsyncClient = field(repr=False)
    endpoint: str
    model: str
    voice: str
    speed: float = 1.0
    api_key: SecretStr | None = field(default=None, repr=False)
    gain: float = 0.65
    leading_silence_ms: int = 0
    trailing_silence_ms: int = 0

    async def synthesize(self, text: str) -> TtsResult:
        if not text.strip():
            raise ValueError("TTS text cannot be empty")
        return await _synthesize_http_wav(
            self.client,
            endpoint=self.endpoint,
            payload={
                "model": self.model,
                "input": text,
                "voice": self.voice,
                "speed": self.speed,
                "response_format": "wav",
            },
            provider="openai",
            api_key=self.api_key,
            gain=self.gain,
            leading_silence_ms=self.leading_silence_ms,
            trailing_silence_ms=self.trailing_silence_ms,
        )


@dataclass(slots=True)
class VoicevoxTtsAdapter:
    client: httpx.AsyncClient = field(repr=False)
    speaker: int = 1
    gain: float = 0.65
    leading_silence_ms: int = 0
    trailing_silence_ms: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.speaker <= 1_000:
            raise ValueError("VOICEVOX speaker must be between 0 and 1000")

    async def synthesize(self, text: str) -> TtsResult:
        if not text.strip():
            raise ValueError("TTS text cannot be empty")
        params = {"speaker": self.speaker}
        try:
            async with self.client.stream(
                "POST",
                "/audio_query",
                params={**params, "text": text},
            ) as query_response:
                query_response.raise_for_status()
                query_body = await _read_bounded_response(
                    query_response,
                    maximum_bytes=_MAX_VOICEVOX_QUERY_BYTES,
                    error_message="VOICEVOX audio query exceeds the size limit",
                )
            query = json.loads(query_body)
            if not isinstance(query, dict):
                raise TtsProviderError("VOICEVOX audio query is invalid")
            async with self.client.stream(
                "POST",
                "/synthesis",
                params=params,
                headers={"Accept": "audio/wav"},
                json=query,
            ) as synthesis_response:
                synthesis_response.raise_for_status()
                if not synthesis_response.headers.get("content-type", "").startswith("audio/wav"):
                    raise TtsProviderError("VOICEVOX did not return WAV audio")
                wav = await _read_bounded_response(
                    synthesis_response,
                    maximum_bytes=_MAX_WAV_RESPONSE_BYTES,
                    error_message="VOICEVOX WAV response exceeds the size limit",
                )
            _validate_wav_limits(
                wav,
                leading_silence_ms=self.leading_silence_ms,
                trailing_silence_ms=self.trailing_silence_ms,
                provider="VOICEVOX",
            )
            samples, source_rate = soundfile.read(
                BytesIO(wav),
                dtype="float64",
                always_2d=True,
            )
        except httpx.HTTPStatusError as error:
            raise TtsProviderError(
                "VOICEVOX returned an HTTP error",
                status_code=error.response.status_code,
            ) from error
        except httpx.HTTPError as error:
            raise TtsProviderError("VOICEVOX transport failed") from error
        except TtsProviderError:
            raise
        except (RuntimeError, ValueError) as error:
            raise TtsProviderError("VOICEVOX response was invalid") from error
        if not isinstance(samples, np.ndarray) or not isinstance(source_rate, int):
            raise TtsProviderError("VOICEVOX returned invalid WAV audio")
        audio = normalize_audio(
            samples,
            sample_rate=source_rate,
            gain=self.gain,
            leading_silence_ms=self.leading_silence_ms,
            trailing_silence_ms=self.trailing_silence_ms,
        )
        return TtsResult(
            audio=audio,
            provider_metadata={
                "provider": "voicevox",
                "speaker": self.speaker,
                "source_rate": source_rate,
            },
        )


async def _synthesize_http_wav(
    client: httpx.AsyncClient,
    *,
    endpoint: str,
    payload: dict[str, JsonValue],
    provider: str,
    api_key: SecretStr | None,
    gain: float,
    leading_silence_ms: int,
    trailing_silence_ms: int,
) -> TtsResult:
    headers = {"Accept": "audio/wav"}
    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key.get_secret_value()}"
    try:
        async with client.stream(
            "POST",
            endpoint,
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()
            if not response.headers.get("content-type", "").startswith("audio/wav"):
                raise TtsProviderError("TTS provider did not return WAV audio")
            wav = await _read_bounded_response(
                response,
                maximum_bytes=_MAX_WAV_RESPONSE_BYTES,
                error_message="TTS WAV response exceeds the size limit",
            )
        _validate_wav_limits(
            wav,
            leading_silence_ms=leading_silence_ms,
            trailing_silence_ms=trailing_silence_ms,
            provider="TTS",
        )
        samples, source_rate = soundfile.read(BytesIO(wav), dtype="float64", always_2d=True)
        if not isinstance(samples, np.ndarray) or not isinstance(source_rate, int):
            raise TtsProviderError("TTS provider returned invalid WAV audio")
        audio = normalize_audio(
            samples,
            sample_rate=source_rate,
            gain=gain,
            leading_silence_ms=leading_silence_ms,
            trailing_silence_ms=trailing_silence_ms,
        )
    except httpx.HTTPStatusError as error:
        raise TtsProviderError(
            "TTS provider returned an HTTP error", status_code=error.response.status_code
        ) from error
    except httpx.HTTPError as error:
        raise TtsProviderError("TTS provider transport failed") from error
    except TtsProviderError:
        raise
    except (RuntimeError, ValueError) as error:
        raise TtsProviderError("TTS provider returned invalid WAV audio") from error
    return TtsResult(
        audio=audio,
        provider_metadata={"provider": provider, "source_rate": source_rate},
    )


async def _read_bounded_response(
    response: httpx.Response,
    *,
    maximum_bytes: int,
    error_message: str,
) -> bytes:
    declared_length = response.headers.get("content-length")
    if declared_length is not None:
        try:
            if int(declared_length) > maximum_bytes:
                raise TtsProviderError(error_message)
        except ValueError:
            pass
    body = bytearray()
    async for chunk in response.aiter_bytes():
        if len(body) + len(chunk) > maximum_bytes:
            raise TtsProviderError(error_message)
        body.extend(chunk)
    return bytes(body)


def _validate_wav_limits(
    wav: bytes,
    *,
    leading_silence_ms: int,
    trailing_silence_ms: int,
    provider: str,
) -> None:
    info = soundfile.info(BytesIO(wav))
    available_duration_ms = _MAX_AUDIO_DURATION_MS - leading_silence_ms - trailing_silence_ms
    if available_duration_ms < 0 or info.frames * 1_000 > available_duration_ms * info.samplerate:
        raise TtsProviderError(f"{provider} WAV exceeds the duration limit")
    if info.frames * info.channels > _MAX_DECODED_SAMPLE_VALUES:
        raise TtsProviderError(f"{provider} WAV exceeds the decoded sample limit")


async def synthesize_with_timeout(
    adapter: TtsAdapter,
    text: str,
    *,
    timeout_seconds: float,
) -> TtsResult:
    if not text.strip():
        raise ValueError("TTS text cannot be empty")
    if timeout_seconds <= 0:
        raise ValueError("TTS timeout must be positive")
    try:
        async with timeout(timeout_seconds):
            return await adapter.synthesize(text)
    except builtins.TimeoutError as error:
        raise TtsTimeoutError("speech synthesis timed out") from error
