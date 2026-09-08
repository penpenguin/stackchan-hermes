from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.hermes.client import HermesClient, HermesClientConfig
from stackchan_bridge.hermes.errors import HermesError
from stackchan_bridge.stt.adapters import GenericHttpSttAdapter
from stackchan_bridge.stt.errors import SttProviderError
from stackchan_bridge.tts.adapters import (
    GenericHttpWavTtsAdapter,
    OpenAICompatibleTtsAdapter,
    VoicevoxTtsAdapter,
)
from stackchan_bridge.tts.errors import TtsProviderError


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize(
    "provider", ["stt", "wav", "openai", "voicevox-query", "voicevox-synthesis", "hermes", "probe"]
)
async def test_private_payloads_and_credentials_never_follow_redirects(
    provider: str, status: int
) -> None:
    requests: list[httpx.Request] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        await request.aread()
        requests.append(request)
        if request.url.host == "other.example.test":
            return httpx.Response(400)
        if provider == "voicevox-synthesis" and request.url.path == "/audio_query":
            return httpx.Response(200, json={"accent_phrases": []})
        return httpx.Response(status, headers={"Location": "https://other.example.test/stolen"})

    # The adapter must enforce policy even if an injected/shared client enables redirects.
    async with httpx.AsyncClient(
        base_url="https://configured.example.test",
        transport=httpx.MockTransport(handle),
        follow_redirects=True,
    ) as client:
        key = SecretStr("test-provider-key")  # pragma: allowlist secret
        if provider == "stt":
            with pytest.raises(SttProviderError):
                await GenericHttpSttAdapter(client, "/transcribe", api_key=key).transcribe(
                    PcmAudio(pcm=b"\x00\x00" * 160)
                )
        elif provider in {"wav", "openai", "voicevox-query", "voicevox-synthesis"}:
            adapter: GenericHttpWavTtsAdapter | OpenAICompatibleTtsAdapter | VoicevoxTtsAdapter
            if provider == "wav":
                adapter = GenericHttpWavTtsAdapter(client, "/speech", api_key=key)
            elif provider == "openai":
                adapter = OpenAICompatibleTtsAdapter(
                    client, "/speech", "model", "voice", api_key=key
                )
            else:
                adapter = VoicevoxTtsAdapter(client)
            with pytest.raises(TtsProviderError):
                await adapter.synthesize("private transcript")
        else:
            hermes = HermesClient(client, HermesClientConfig(api_key=key, model="hermes-agent"))
            if provider == "probe":
                assert not (await hermes.probe()).ready
            else:
                with pytest.raises(HermesError):
                    async for _ in hermes.stream_vision_response(
                        device_id="sim-001",
                        question="private question",
                        jpeg=b"\xff\xd8\xff\x00\xff\xd9",
                    ):
                        pass
    assert requests
    assert all(request.url.host == "configured.example.test" for request in requests)
    assert len(requests) == (2 if provider == "voicevox-synthesis" else 1)
