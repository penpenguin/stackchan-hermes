from __future__ import annotations

import asyncio
from asyncio import CancelledError, Event
from collections.abc import AsyncIterator
from dataclasses import dataclass
from threading import Event as ThreadEvent
from threading import get_ident

import httpx
import pytest
from pydantic import SecretStr
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.stt.adapters import (
    FasterWhisperSttAdapter,
    GenericHttpSttAdapter,
    MockSttAdapter,
    SttResult,
    transcribe_with_timeout,
)
from stackchan_bridge.stt.errors import SttProviderError, SttTimeoutError


def silent_audio(duration_ms: int = 1_000) -> PcmAudio:
    return PcmAudio(
        pcm=b"\x00\x00" * (16_000 * duration_ms // 1_000),
        sample_rate=16_000,
        channels=1,
    )


@pytest.mark.asyncio
async def test_mock_stt_returns_typed_result_and_allows_an_empty_transcript() -> None:
    spoken = MockSttAdapter(text="こんにちは", language="ja", confidence=0.9)
    empty = MockSttAdapter(text="", language="ja", confidence=None)

    spoken_result = await transcribe_with_timeout(spoken, silent_audio(), timeout_seconds=1)
    empty_result = await transcribe_with_timeout(empty, silent_audio(), timeout_seconds=1)

    assert spoken_result == SttResult(
        text="こんにちは",
        language="ja",
        confidence=0.9,
        audio_duration_seconds=1.0,
        provider_metadata={"provider": "mock"},
    )
    assert empty_result.text == ""
    assert empty_result.is_empty is True


class BlockingSttAdapter:
    def __init__(self) -> None:
        self.cancelled = Event()

    async def transcribe(self, audio: PcmAudio) -> SttResult:
        try:
            await Event().wait()
        except CancelledError:
            self.cancelled.set()
            raise
        raise AssertionError("unreachable")


class ChunkedResponseStream(httpx.AsyncByteStream):
    def __init__(self, chunks: tuple[bytes, ...]) -> None:
        self._chunks = chunks
        self.chunks_read = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            self.chunks_read += 1
            yield chunk

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_stt_timeout_cancels_the_provider_task() -> None:
    adapter = BlockingSttAdapter()

    with pytest.raises(SttTimeoutError):
        await transcribe_with_timeout(adapter, silent_audio(), timeout_seconds=0.001)

    assert adapter.cancelled.is_set()


@pytest.mark.asyncio
async def test_generic_http_stt_sends_authenticated_wav_and_parses_result() -> None:
    api_key = "stt-runtime-key"  # pragma: allowlist secret

    async def handle(request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        assert request.headers["authorization"] == f"Bearer {api_key}"
        assert request.headers["content-type"].startswith("multipart/form-data;")
        assert b"RIFF" in body
        assert b"WAVE" in body
        return httpx.Response(
            200,
            json={
                "text": "テストです",
                "language": "ja",
                "confidence": 0.8,
                "metadata": {"request_id": "stt-1"},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = GenericHttpSttAdapter(
            client,
            endpoint="http://127.0.0.1:9000/transcribe",
            api_key=SecretStr(api_key),
            language="ja",
        )
        result = await adapter.transcribe(silent_audio(500))

    assert result.text == "テストです"
    assert result.confidence == 0.8
    assert result.audio_duration_seconds == 0.5
    assert result.provider_metadata == {"provider": "http", "request_id": "stt-1"}
    assert api_key not in repr(adapter)


@pytest.mark.asyncio
async def test_generic_http_stt_stops_reading_an_oversized_json_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "stackchan_bridge.stt.adapters._MAX_JSON_RESPONSE_BYTES",
        4,
        raising=False,
    )
    stream = ChunkedResponseStream((b'{"t', b"ex", b't":"must-not-be-read"}'))

    async def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            stream=stream,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = GenericHttpSttAdapter(
            client,
            endpoint="https://stt.example.test/transcribe",
        )
        with pytest.raises(SttProviderError, match="size limit"):
            await adapter.transcribe(silent_audio(100))

    assert stream.chunks_read == 2


@dataclass(frozen=True)
class FakeSegment:
    text: str
    avg_logprob: float


@dataclass(frozen=True)
class FakeWhisperInfo:
    language: str
    language_probability: float


class FakeWhisperModel:
    def transcribe(
        self,
        samples: object,
        *,
        language: str,
        vad_filter: bool,
    ) -> tuple[list[FakeSegment], FakeWhisperInfo]:
        assert language == "ja"
        assert vad_filter is False
        return (
            [FakeSegment(" こんにちは", -0.1), FakeSegment(" 世界 ", -0.2)],
            FakeWhisperInfo(language="ja", language_probability=0.95),
        )


@pytest.mark.asyncio
async def test_faster_whisper_adapter_loads_off_loop_once_and_joins_segments() -> None:
    test_thread = get_ident()
    loader_threads: list[int] = []

    def load_model(model_name: str, device: str, compute_type: str) -> FakeWhisperModel:
        assert (model_name, device, compute_type) == ("tiny", "cpu", "int8")
        loader_threads.append(get_ident())
        return FakeWhisperModel()

    adapter = FasterWhisperSttAdapter(
        model_name="tiny",
        language="ja",
        device="cpu",
        compute_type="int8",
        model_factory=load_model,
    )

    first = await adapter.transcribe(silent_audio(500))
    second = await adapter.transcribe(silent_audio(500))

    assert first.text == "こんにちは 世界"
    assert first.language == "ja"
    assert first.confidence == 0.95
    assert second.text == first.text
    assert len(loader_threads) == 1
    assert loader_threads[0] != test_thread


@pytest.mark.asyncio
@pytest.mark.parametrize("load_fails", [False, True])
async def test_faster_whisper_shares_model_loading_after_cancellation(load_fails: bool) -> None:
    started = ThreadEvent()
    release = ThreadEvent()
    calls = 0

    def load_model(_model: str, _device: str, _compute: str) -> FakeWhisperModel:
        nonlocal calls
        calls += 1
        started.set()
        assert release.wait(timeout=2)
        if load_fails and calls == 1:
            raise RuntimeError("model load failed")
        return FakeWhisperModel()

    adapter = FasterWhisperSttAdapter(model_name="tiny", model_factory=load_model)
    pending = asyncio.create_task(adapter.transcribe(silent_audio(20)))
    try:
        assert await asyncio.to_thread(started.wait, 1)
        for _ in range(3):
            pending.cancel()
            with pytest.raises(CancelledError):
                await pending
            pending = asyncio.create_task(adapter.transcribe(silent_audio(20)))
            await asyncio.sleep(0.02)
            assert calls == 1
        release.set()
        if load_fails:
            with pytest.raises(SttProviderError, match="model is unavailable"):
                await asyncio.wait_for(pending, timeout=1)
        else:
            assert (await asyncio.wait_for(pending, timeout=1)).text == "こんにちは 世界"
        assert (await adapter.transcribe(silent_audio(20))).text == "こんにちは 世界"
        assert calls == (2 if load_fails else 1)
    finally:
        release.set()
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)


@pytest.mark.asyncio
async def test_faster_whisper_does_not_overlap_inference_after_cancellation() -> None:
    first_started = ThreadEvent()
    release_first = ThreadEvent()
    calls = 0

    class BlockingFirstWhisperModel:
        def transcribe(
            self,
            samples: object,
            *,
            language: str,
            vad_filter: bool,
        ) -> tuple[list[FakeSegment], FakeWhisperInfo]:
            nonlocal calls
            calls += 1
            if calls == 1:
                first_started.set()
                assert release_first.wait(timeout=2)
            return [FakeSegment("完了", -0.1)], FakeWhisperInfo("ja", 0.9)

    adapter = FasterWhisperSttAdapter(
        model_name="tiny",
        model_factory=lambda _model, _device, _compute: BlockingFirstWhisperModel(),
    )
    first = asyncio.create_task(adapter.transcribe(silent_audio(20)))
    assert await asyncio.to_thread(first_started.wait, 1)

    first.cancel()
    with pytest.raises(CancelledError):
        await first
    second = asyncio.create_task(adapter.transcribe(silent_audio(20)))
    await asyncio.sleep(0.05)

    assert calls == 1
    release_first.set()
    result = await asyncio.wait_for(second, timeout=1)
    assert calls == 2
    assert result.text == "完了"
