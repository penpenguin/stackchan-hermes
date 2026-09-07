from __future__ import annotations

import json
from asyncio import CancelledError, Event, create_task, wait_for
from collections.abc import AsyncIterator
from io import BytesIO
from wave import open as open_wave

import httpx
import numpy as np
import pytest
from pydantic import SecretStr
from stackchan_bridge.tts.adapters import (
    GenericHttpWavTtsAdapter,
    OpenAICompatibleTtsAdapter,
    synthesize_with_timeout,
)
from stackchan_bridge.tts.errors import TtsProviderError, TtsTimeoutError


def make_wav(*, sample_rate: int = 24_000, frames: int = 12_000) -> bytes:
    times = np.arange(frames) / sample_rate
    mono = np.sin(2 * np.pi * 440 * times) * 12_000
    stereo = np.column_stack((mono, mono)).astype("<i2")
    buffer = BytesIO()
    with open_wave(buffer, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(stereo.tobytes())
    return buffer.getvalue()


async def test_openai_tts_posts_speech_request_and_normalizes_wav() -> None:
    endpoint = "http://127.0.0.1:8088/v1/audio/speech"
    wav = make_wav()

    async def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == endpoint
        assert request.headers["accept"] == "audio/wav"
        assert request.headers["content-type"] == "application/json"
        assert "authorization" not in request.headers
        assert json.loads(await request.aread()) == {
            "model": "irodori-tts",
            "input": "こんにちは。",
            "voice": "sample",
            "speed": 1.0,
            "response_format": "wav",
        }
        return httpx.Response(200, content=wav, headers={"Content-Type": "audio/wav"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = OpenAICompatibleTtsAdapter(
            client,
            endpoint=endpoint,
            model="irodori-tts",
            voice="sample",
            gain=0.5,
            leading_silence_ms=100,
            trailing_silence_ms=200,
        )
        result = await adapter.synthesize("こんにちは。")

    assert result.audio.sample_rate == 16_000
    assert result.audio.channels == 1
    assert result.audio.duration_seconds == 0.8
    samples = np.frombuffer(result.audio.pcm, dtype="<i2")
    assert np.all(samples[:1_600] == 0)
    assert np.all(samples[-3_200:] == 0)
    assert np.max(np.abs(samples)) == pytest.approx(6_000, abs=2)
    assert result.provider_metadata == {"provider": "openai", "source_rate": 24_000}


async def test_openai_tts_sends_configured_model_voice_speed_and_bearer_token() -> None:
    api_key = "runtime-speech-key"  # pragma: allowlist secret
    endpoint = "https://tts.example.test/prefix/v1/audio/speech"

    async def handle(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == endpoint
        assert request.headers["authorization"] == f"Bearer {api_key}"
        assert json.loads(await request.aread()) == {
            "model": "custom-model",
            "voice": "registered-voice",
            "speed": 1.25,
            "input": "次の文です。",
            "response_format": "wav",
        }
        return httpx.Response(
            200, content=make_wav(), headers={"Content-Type": "audio/wav; charset=binary"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = OpenAICompatibleTtsAdapter(
            client,
            endpoint=endpoint,
            model="custom-model",
            voice="registered-voice",
            speed=1.25,
            api_key=SecretStr(api_key),
        )
        result = await adapter.synthesize("次の文です。")

    assert api_key not in repr(adapter)
    assert api_key not in repr(result)


@pytest.mark.parametrize(
    ("caption", "seed", "expected_options"),
    [
        (None, None, {}),
        ("穏やかに話す。", None, {"caption": "穏やかに話す。"}),
        (None, 0, {"seed": 0}),
        ("", None, {"caption": ""}),
        ("明るい声。", 1234, {"caption": "明るい声。", "seed": 1234}),
    ],
)
async def test_openai_tts_sends_only_configured_irodori_options(
    caption: str | None, seed: int | None, expected_options: dict[str, str | int]
) -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        payload = json.loads(await request.aread())
        if expected_options:
            assert payload.pop("irodori") == expected_options
        assert payload == {
            "model": "irodori-tts",
            "input": "こんにちは。",
            "voice": "sample",
            "speed": 1.0,
            "response_format": "wav",
        }
        return httpx.Response(200, content=make_wav(), headers={"Content-Type": "audio/wav"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = OpenAICompatibleTtsAdapter(
            client,
            endpoint="http://127.0.0.1:8088/v1/audio/speech",
            model="irodori-tts",
            voice="sample",
            irodori_caption=caption,
            irodori_seed=seed,
        )

        await adapter.synthesize("こんにちは。")


@pytest.mark.parametrize("text", ["", " \n\t"])
async def test_openai_tts_rejects_empty_text_without_request(text: str) -> None:
    def reject_request(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("empty speech must not call the provider")

    async with httpx.AsyncClient(transport=httpx.MockTransport(reject_request)) as client:
        adapter = OpenAICompatibleTtsAdapter(
            client,
            endpoint="http://127.0.0.1:8088/v1/audio/speech",
            model="irodori-tts",
            voice="sample",
        )
        with pytest.raises(ValueError, match="empty"):
            await adapter.synthesize(text)


@pytest.mark.parametrize(
    ("status_code", "content_type"),
    [(401, "application/json"), (503, "text/plain"), (200, "audio/mpeg"), (200, "audio/wav")],
)
async def test_openai_tts_maps_provider_errors_without_body_reflection(
    status_code: int, content_type: str
) -> None:
    private_body = b"private-provider-diagnostic"

    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code, content=private_body, headers={"Content-Type": content_type}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = OpenAICompatibleTtsAdapter(
            client,
            endpoint="http://127.0.0.1:8088/v1/audio/speech",
            model="irodori-tts",
            voice="sample",
        )
        with pytest.raises(TtsProviderError) as raised:
            await adapter.synthesize("こんにちは。")

    assert raised.value.status_code == (status_code if status_code >= 400 else None)
    assert private_body.decode() not in str(raised.value)


async def test_openai_tts_maps_transport_failure_without_diagnostic_reflection() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private-transport-diagnostic", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = OpenAICompatibleTtsAdapter(
            client,
            endpoint="http://127.0.0.1:8088/v1/audio/speech",
            model="irodori-tts",
            voice="sample",
        )
        with pytest.raises(TtsProviderError) as raised:
            await adapter.synthesize("こんにちは。")

    assert "private-transport-diagnostic" not in str(raised.value)


@pytest.mark.parametrize("provider", ["http", "openai"])
async def test_http_wav_tts_maps_empty_audio_to_provider_error(provider: str) -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=make_wav(frames=0), headers={"Content-Type": "audio/wav"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        endpoint = "http://127.0.0.1:8088/v1/audio/speech"
        adapter = (
            OpenAICompatibleTtsAdapter(client, endpoint, model="irodori-tts", voice="sample")
            if provider == "openai"
            else GenericHttpWavTtsAdapter(client, endpoint)
        )
        with pytest.raises(TtsProviderError, match="invalid WAV"):
            await adapter.synthesize("こんにちは。")


class TrackedResponseStream(httpx.AsyncByteStream):
    def __init__(self, chunks: tuple[bytes, ...], *, block: bool = False) -> None:
        self.chunks = chunks
        self.block = block
        self.chunks_read = 0
        self.started = Event()
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        self.started.set()
        for chunk in self.chunks:
            self.chunks_read += 1
            yield chunk
        if self.block:
            await Event().wait()

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.parametrize("declared_length", [None, "100"])
async def test_openai_tts_bounds_wav_download_and_closes_stream(
    monkeypatch: pytest.MonkeyPatch, declared_length: str | None
) -> None:
    monkeypatch.setattr("stackchan_bridge.tts.adapters._MAX_WAV_RESPONSE_BYTES", 4)
    stream = TrackedResponseStream((b"123", b"45", b"must-not-read"))
    headers = {"Content-Type": "audio/wav"}
    if declared_length is not None:
        headers["Content-Length"] = declared_length

    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers=headers, stream=stream)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = OpenAICompatibleTtsAdapter(
            client,
            endpoint="http://127.0.0.1:8088/v1/audio/speech",
            model="irodori-tts",
            voice="sample",
        )
        with pytest.raises(TtsProviderError, match="size limit"):
            await adapter.synthesize("こんにちは。")

    assert stream.chunks_read == (0 if declared_length else 2)
    assert stream.closed


@pytest.mark.parametrize("limit", ["duration", "padding", "decoded"])
async def test_openai_tts_checks_audio_limits_before_decoding(
    monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    if limit == "decoded":
        monkeypatch.setattr("stackchan_bridge.tts.adapters._MAX_DECODED_SAMPLE_VALUES", 8)
        wav = make_wav(frames=5)
    else:
        wav = make_wav(sample_rate=1, frames=120 if limit == "padding" else 121)

    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=wav, headers={"Content-Type": "audio/wav"})

    def reject_decode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("audio limits must be checked before decoding")

    monkeypatch.setattr("stackchan_bridge.tts.adapters.soundfile.read", reject_decode)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = OpenAICompatibleTtsAdapter(
            client,
            endpoint="http://127.0.0.1:8088/v1/audio/speech",
            model="irodori-tts",
            voice="sample",
            leading_silence_ms=1 if limit == "padding" else 0,
        )
        with pytest.raises(TtsProviderError, match="limit"):
            await adapter.synthesize("こんにちは。")


@pytest.mark.parametrize("interrupt", ["timeout", "cancel"])
async def test_openai_tts_releases_response_on_timeout_or_cancellation(interrupt: str) -> None:
    stream = TrackedResponseStream((b"RIFF",), block=True)

    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=stream, headers={"Content-Type": "audio/wav"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = OpenAICompatibleTtsAdapter(
            client,
            endpoint="http://127.0.0.1:8088/v1/audio/speech",
            model="irodori-tts",
            voice="sample",
        )
        task = create_task(synthesize_with_timeout(adapter, "こんにちは。", timeout_seconds=0.1))
        await wait_for(stream.started.wait(), timeout=1)
        if interrupt == "cancel":
            task.cancel()
        with pytest.raises(CancelledError if interrupt == "cancel" else TtsTimeoutError):
            await task

    assert stream.closed
