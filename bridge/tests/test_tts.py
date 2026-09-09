from __future__ import annotations

from asyncio import CancelledError, Event
from collections.abc import AsyncIterator, Callable
from io import BytesIO
from wave import open as open_wave

import httpx
import numpy as np
import pytest
from pydantic import SecretStr
from stackchan_bridge.audio.normalize import normalize_audio
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.tts.adapters import (
    GenericHttpWavTtsAdapter,
    MockTtsAdapter,
    OpenAICompatibleTtsAdapter,
    TtsAdapter,
    TtsResult,
    VoicevoxTtsAdapter,
    synthesize_with_timeout,
)
from stackchan_bridge.tts.errors import TtsProviderError, TtsTimeoutError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "factory",
    [
        pytest.param(
            lambda client: GenericHttpWavTtsAdapter(client, endpoint="/synthesize"),
            id="http-wav",
        ),
        pytest.param(
            lambda client: OpenAICompatibleTtsAdapter(
                client, endpoint="/v1/audio/speech", model="irodori-tts", voice="sample"
            ),
            id="openai",
        ),
        pytest.param(lambda client: VoicevoxTtsAdapter(client), id="voicevox"),
    ],
)
async def test_tts_default_gain_preserves_provider_amplitude(
    factory: Callable[[httpx.AsyncClient], TtsAdapter],
) -> None:
    samples = np.tile(np.array([12_000, -12_000], dtype="<i2"), 480)
    wav_buffer = BytesIO()
    with open_wave(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16_000)
        wav_file.writeframes(samples.tobytes())

    async def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/audio_query":
            return httpx.Response(200, json={"speedScale": 1.0})
        return httpx.Response(
            200, content=wav_buffer.getvalue(), headers={"Content-Type": "audio/wav"}
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle), base_url="http://127.0.0.1:50021"
    ) as client:
        result = await factory(client).synthesize("こんにちは")

    np.testing.assert_allclose(np.frombuffer(result.audio.pcm, dtype="<i2"), samples, atol=1)


@pytest.mark.asyncio
async def test_mock_tts_returns_deterministic_normalized_audio() -> None:
    adapter = MockTtsAdapter(milliseconds_per_character=80, minimum_duration_ms=200)

    first = await synthesize_with_timeout(adapter, "こんにちは", timeout_seconds=1)
    second = await synthesize_with_timeout(adapter, "こんにちは", timeout_seconds=1)

    assert isinstance(first, TtsResult)
    assert first.audio.sample_rate == 16_000
    assert first.audio.channels == 1
    assert first.audio.duration_seconds == 0.4
    assert first.audio.pcm == second.audio.pcm
    assert np.frombuffer(first.audio.pcm, dtype="<i2").std() > 100
    assert first.provider_metadata == {"provider": "mock"}


class BlockingTtsAdapter:
    def __init__(self) -> None:
        self.cancelled = Event()

    async def synthesize(self, text: str) -> TtsResult:
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
async def test_tts_timeout_cancels_the_provider_task() -> None:
    adapter = BlockingTtsAdapter()

    with pytest.raises(TtsTimeoutError):
        await synthesize_with_timeout(adapter, "こんにちは", timeout_seconds=0.001)

    assert adapter.cancelled.is_set()


def test_pcm_audio_rejects_non_normalized_provider_output() -> None:
    with pytest.raises(ValueError, match="16000"):
        PcmAudio(pcm=b"\x00\x00", sample_rate=24_000, channels=1)


def test_audio_normalizer_downmixes_resamples_removes_dc_and_adds_silence() -> None:
    source_rate = 24_000
    times = np.arange(source_rate, dtype=np.float64) / source_rate
    left = 0.2 + 0.5 * np.sin(2 * np.pi * 440 * times)
    right = 0.2 + 0.25 * np.sin(2 * np.pi * 440 * times)
    stereo = np.column_stack((left, right))

    normalized = normalize_audio(
        stereo,
        sample_rate=source_rate,
        gain=0.65,
        leading_silence_ms=100,
        trailing_silence_ms=100,
    )
    samples = np.frombuffer(normalized.pcm, dtype="<i2")

    assert normalized.duration_seconds == 1.2
    assert np.all(samples[:1_600] == 0)
    assert np.all(samples[-1_600:] == 0)
    voice = samples[1_600:-1_600]
    assert abs(float(voice.mean())) < 2
    assert 1_000 < voice.std() < 20_000


@pytest.mark.asyncio
async def test_generic_http_wav_tts_normalizes_authenticated_provider_audio() -> None:
    api_key = "tts-runtime-key"  # pragma: allowlist secret
    source_rate = 24_000
    times = np.arange(source_rate // 2, dtype=np.float64) / source_rate
    mono = np.sin(2 * np.pi * 440 * times) * 12_000
    stereo = np.column_stack((mono, mono)).astype("<i2")
    wav_buffer = BytesIO()
    with open_wave(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(source_rate)
        wav_file.writeframes(stereo.tobytes())

    async def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {api_key}"
        assert '"text":"こんにちは"'.encode() in await request.aread()
        return httpx.Response(
            200,
            content=wav_buffer.getvalue(),
            headers={"Content-Type": "audio/wav"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = GenericHttpWavTtsAdapter(
            client,
            endpoint="http://127.0.0.1:9001/synthesize",
            api_key=SecretStr(api_key),
            gain=0.65,
            leading_silence_ms=100,
            trailing_silence_ms=100,
        )
        result = await adapter.synthesize("こんにちは")

    assert result.audio.duration_seconds == 0.7
    assert result.provider_metadata == {"provider": "http-wav", "source_rate": 24_000}
    assert api_key not in repr(adapter)


@pytest.mark.asyncio
async def test_voicevox_tts_uses_audio_query_then_synthesis() -> None:
    source_rate = 24_000
    samples = (np.sin(2 * np.pi * 330 * np.arange(2_400) / source_rate) * 10_000).astype("<i2")
    wav_buffer = BytesIO()
    with open_wave(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(source_rate)
        wav_file.writeframes(samples.tobytes())
    calls: list[str] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.url.params["speaker"] == "3"
        if request.url.path == "/audio_query":
            assert request.url.params["text"] == "こんにちは"
            return httpx.Response(200, json={"speedScale": 1.0, "kana": "コンニチハ"})
        assert request.url.path == "/synthesis"
        assert b'"speedScale":1.0' in await request.aread()
        return httpx.Response(
            200,
            content=wav_buffer.getvalue(),
            headers={"Content-Type": "audio/wav"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle),
        base_url="http://127.0.0.1:50021",
    ) as client:
        adapter = VoicevoxTtsAdapter(client, speaker=3, gain=0.65)
        result = await adapter.synthesize("こんにちは")

    assert calls == ["/audio_query", "/synthesis"]
    assert result.audio.sample_rate == 16_000
    assert result.provider_metadata == {
        "provider": "voicevox",
        "speaker": 3,
        "source_rate": 24_000,
    }


@pytest.mark.parametrize(
    "factory",
    [
        lambda: MockTtsAdapter(milliseconds_per_character=0),
        lambda: MockTtsAdapter(minimum_duration_ms=200, maximum_duration_ms=100),
        lambda: MockTtsAdapter(frequency_hz=0),
    ],
)
def test_mock_tts_rejects_invalid_synthesis_configuration(factory: object) -> None:
    with pytest.raises(ValueError):
        factory()  # type: ignore[operator]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "content_type"),
    [(503, "text/plain"), (200, "application/json")],
)
async def test_generic_http_tts_maps_provider_failures_without_body_reflection(
    status_code: int,
    content_type: str,
) -> None:
    private_body = b"private-provider-diagnostic"

    async def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            content=private_body,
            headers={"Content-Type": content_type},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = GenericHttpWavTtsAdapter(client, endpoint="https://tts.example.test/speech")
        with pytest.raises(TtsProviderError) as raised:
            await adapter.synthesize("こんにちは")

    assert "private-provider-diagnostic" not in str(raised.value)
    if status_code == 503:
        assert raised.value.status_code == 503


@pytest.mark.asyncio
async def test_generic_http_tts_stops_reading_an_oversized_wav_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "stackchan_bridge.tts.adapters._MAX_WAV_RESPONSE_BYTES",
        4,
    )
    stream = ChunkedResponseStream((b"123", b"45", b"must-not-be-read"))

    async def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "audio/wav"},
            stream=stream,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = GenericHttpWavTtsAdapter(client, endpoint="https://tts.example.test/speech")
        with pytest.raises(TtsProviderError, match="size limit"):
            await adapter.synthesize("こんにちは")

    assert stream.chunks_read == 2


@pytest.mark.asyncio
async def test_generic_http_tts_rejects_excessive_wav_duration_before_decoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wav_buffer = BytesIO()
    with open_wave(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(1)
        wav_file.writeframes(b"\x00\x00" * 121)

    async def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=wav_buffer.getvalue(),
            headers={"Content-Type": "audio/wav"},
        )

    def fail_if_decoded(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("oversized WAV must be rejected before decoding")

    monkeypatch.setattr("stackchan_bridge.tts.adapters.soundfile.read", fail_if_decoded)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = GenericHttpWavTtsAdapter(client, endpoint="https://tts.example.test/speech")
        with pytest.raises(TtsProviderError, match="duration limit"):
            await adapter.synthesize("こんにちは")


@pytest.mark.asyncio
async def test_voicevox_tts_stops_reading_an_oversized_wav_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "stackchan_bridge.tts.adapters._MAX_WAV_RESPONSE_BYTES",
        4,
    )
    stream = ChunkedResponseStream((b"123", b"45", b"must-not-be-read"))

    async def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/audio_query":
            return httpx.Response(200, json={"speedScale": 1.0})
        return httpx.Response(
            200,
            headers={"Content-Type": "audio/wav"},
            stream=stream,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle),
        base_url="http://127.0.0.1:50021",
    ) as client:
        adapter = VoicevoxTtsAdapter(client)
        with pytest.raises(TtsProviderError, match="size limit"):
            await adapter.synthesize("こんにちは")

    assert stream.chunks_read == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["oversized_query", "wrong_mime"])
async def test_voicevox_rejects_bounded_or_non_wav_provider_responses(scenario: str) -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/audio_query":
            if scenario == "oversized_query":
                return httpx.Response(200, content=b"x" * 262_145)
            return httpx.Response(200, json={"speedScale": 1.0})
        return httpx.Response(
            200,
            content=b"not-wav",
            headers={"Content-Type": "application/octet-stream"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle),
        base_url="http://127.0.0.1:50021",
    ) as client:
        adapter = VoicevoxTtsAdapter(client)
        with pytest.raises(TtsProviderError):
            await adapter.synthesize("こんにちは")
