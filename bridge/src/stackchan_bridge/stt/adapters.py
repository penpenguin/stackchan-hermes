"""Provider-neutral STT contract and deterministic mock."""

from __future__ import annotations

import builtins
import json
from asyncio import CancelledError, Lock, Task, create_task, shield, timeout, to_thread
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Protocol, cast

import httpx
import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, JsonValue, SecretStr, ValidationError

from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.audio.wav import pcm_to_wav
from stackchan_bridge.stt.errors import SttProviderError, SttTimeoutError

_MAX_JSON_RESPONSE_BYTES = 1_048_576


@dataclass(frozen=True, slots=True)
class SttResult:
    text: str
    language: str
    confidence: float | None
    audio_duration_seconds: float
    provider_metadata: dict[str, JsonValue]

    def __post_init__(self) -> None:
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("STT confidence must be between zero and one")
        if self.audio_duration_seconds < 0:
            raise ValueError("audio duration cannot be negative")

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class SttAdapter(Protocol):
    async def transcribe(self, audio: PcmAudio) -> SttResult: ...


class WhisperSegment(Protocol):
    text: str
    avg_logprob: float


class WhisperInfo(Protocol):
    language: str
    language_probability: float


class WhisperModel(Protocol):
    def transcribe(
        self,
        samples: NDArray[np.float32],
        *,
        language: str,
        vad_filter: bool,
    ) -> tuple[Iterable[WhisperSegment], WhisperInfo]: ...


WhisperModelFactory = Callable[[str, str, str], WhisperModel]


def _default_whisper_model(model_name: str, device: str, compute_type: str) -> WhisperModel:
    try:
        from faster_whisper import (  # type: ignore[import-not-found]
            WhisperModel as LibraryWhisperModel,
        )
    except ImportError as error:
        raise SttProviderError("faster-whisper optional dependency is not installed") from error
    return cast(
        WhisperModel,
        LibraryWhisperModel(model_name, device=device, compute_type=compute_type),
    )


@dataclass(frozen=True, slots=True)
class MockSttAdapter:
    text: str = "こんにちは"
    language: str = "ja"
    confidence: float | None = 1.0

    async def transcribe(self, audio: PcmAudio) -> SttResult:
        return SttResult(
            text=self.text,
            language=self.language,
            confidence=self.confidence,
            audio_duration_seconds=audio.duration_seconds,
            provider_metadata={"provider": "mock"},
        )


class _HttpSttResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = Field(max_length=20_000)
    language: str = Field(min_length=1, max_length=32)
    confidence: float | None = Field(default=None, ge=0, le=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict, max_length=32)


@dataclass(slots=True)
class GenericHttpSttAdapter:
    client: httpx.AsyncClient = field(repr=False)
    endpoint: str
    api_key: SecretStr | None = field(default=None, repr=False)
    language: str = "ja"

    async def transcribe(self, audio: PcmAudio) -> SttResult:
        headers: dict[str, str] = {}
        if self.api_key is not None:
            headers["Authorization"] = f"Bearer {self.api_key.get_secret_value()}"
        try:
            async with self.client.stream(
                "POST",
                self.endpoint,
                headers=headers,
                data={"language": self.language},
                files={"file": ("speech.wav", pcm_to_wav(audio), "audio/wav")},
                follow_redirects=False,
            ) as response:
                response.raise_for_status()
                body = await _read_bounded_response(response)
            payload = _HttpSttResponse.model_validate(json.loads(body))
        except httpx.HTTPStatusError as error:
            raise SttProviderError(
                "STT provider returned an HTTP error",
                status_code=error.response.status_code,
            ) from error
        except SttProviderError:
            raise
        except (httpx.HTTPError, ValueError, ValidationError) as error:
            raise SttProviderError("STT provider response was invalid") from error
        return SttResult(
            text=payload.text,
            language=payload.language,
            confidence=payload.confidence,
            audio_duration_seconds=audio.duration_seconds,
            provider_metadata={"provider": "http", **payload.metadata},
        )


async def _read_bounded_response(response: httpx.Response) -> bytes:
    declared_length = response.headers.get("content-length")
    if declared_length is not None:
        try:
            if int(declared_length) > _MAX_JSON_RESPONSE_BYTES:
                raise SttProviderError("STT JSON response exceeds the size limit")
        except ValueError:
            pass
    body = bytearray()
    async for chunk in response.aiter_bytes():
        if len(body) + len(chunk) > _MAX_JSON_RESPONSE_BYTES:
            raise SttProviderError("STT JSON response exceeds the size limit")
        body.extend(chunk)
    return bytes(body)


@dataclass(slots=True)
class FasterWhisperSttAdapter:
    model_name: str
    language: str = "ja"
    device: str = "auto"
    compute_type: str = "default"
    model_factory: WhisperModelFactory = field(default=_default_whisper_model, repr=False)
    _model: WhisperModel | None = field(default=None, init=False, repr=False)
    _model_load: Task[WhisperModel] | None = field(default=None, init=False, repr=False)
    _inference_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    async def transcribe(self, audio: PcmAudio) -> SttResult:
        model = await self._get_model()
        samples: NDArray[np.float32] = np.frombuffer(audio.pcm, dtype="<i2").astype(np.float32)
        samples /= np.float32(32_768)

        def run_model() -> tuple[list[WhisperSegment], WhisperInfo]:
            segments, info = model.transcribe(
                samples,
                language=self.language,
                vad_filter=False,
            )
            return list(segments), info

        try:
            segments, info = await self._run_inference(run_model)
        except Exception as error:
            raise SttProviderError("faster-whisper transcription failed") from error
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        confidence = info.language_probability
        return SttResult(
            text=text,
            language=info.language or self.language,
            confidence=confidence if 0 <= confidence <= 1 else None,
            audio_duration_seconds=audio.duration_seconds,
            provider_metadata={
                "provider": "faster-whisper",
                "model": self.model_name,
                "device": self.device,
                "compute_type": self.compute_type,
            },
        )

    async def _run_inference(
        self,
        run_model: Callable[[], tuple[list[WhisperSegment], WhisperInfo]],
    ) -> tuple[list[WhisperSegment], WhisperInfo]:
        await self._inference_lock.acquire()
        worker = create_task(to_thread(run_model))
        release_when_done = False
        try:
            return await shield(worker)
        except CancelledError:
            release_when_done = True
            worker.add_done_callback(self._release_cancelled_inference)
            raise
        finally:
            if not release_when_done:
                self._inference_lock.release()

    def _release_cancelled_inference(
        self,
        worker: Task[tuple[list[WhisperSegment], WhisperInfo]],
    ) -> None:
        if not worker.cancelled():
            worker.exception()
        self._inference_lock.release()

    async def _get_model(self) -> WhisperModel:
        if self._model is not None:
            return self._model
        if self._model_load is None:
            self._model_load = create_task(self._load_model())
            self._model_load.add_done_callback(self._model_load_finished)
        return await shield(self._model_load)

    async def _load_model(self) -> WhisperModel:
        try:
            self._model = await to_thread(
                self.model_factory,
                self.model_name,
                self.device,
                self.compute_type,
            )
        except Exception as error:
            raise SttProviderError("faster-whisper model is unavailable") from error
        return self._model

    def _model_load_finished(self, worker: Task[WhisperModel]) -> None:
        # Observe failures even when every caller has cancelled; allow a later retry.
        if not worker.cancelled():
            worker.exception()
        self._model_load = None


async def transcribe_with_timeout(
    adapter: SttAdapter,
    audio: PcmAudio,
    *,
    timeout_seconds: float,
) -> SttResult:
    if timeout_seconds <= 0:
        raise ValueError("STT timeout must be positive")
    try:
        async with timeout(timeout_seconds):
            return await adapter.transcribe(audio)
    except builtins.TimeoutError as error:
        raise SttTimeoutError("speech recognition timed out") from error
