# TTS boundary

Typed Mock, generic HTTP WAV, OpenAI-compatible speech, VOICEVOX/Piper-compatible adapters
and normalization belong here.

`adapter = "openai"` posts `model`, `input`, `voice`, `speed`, and `response_format: "wav"`
to the complete configured endpoint, including `/v1/audio/speech`. It supports Irodori's
standard speech API and optional bearer authentication through the named API-key environment
variable. Model and voice are required; speed defaults to 1.0 and accepts 0.25 through 4.0.
Optional `[tts.irodori]` settings accept a string `caption` and an integer `seed`.
Only configured values are sent under the request's `irodori` object; an unset pair
omits the object entirely. Zero is a valid seed. The values apply to every utterance
and segment, and can be overridden through `STACKCHAN_TTS__IRODORI__CAPTION` and
`STACKCHAN_TTS__IRODORI__SEED`. Other Irodori-specific options, voice registration,
and SSE are managed outside this adapter.

The generic HTTP and OpenAI-compatible adapters share bounded WAV download, media validation,
and normalization to 16 kHz mono PCM. Segment ordering, synthesis deadlines, and cancellation
remain in the existing playback pipeline.
