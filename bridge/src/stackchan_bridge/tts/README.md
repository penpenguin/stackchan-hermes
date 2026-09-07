# TTS boundary

Typed Mock, generic HTTP WAV, OpenAI-compatible speech, VOICEVOX/Piper-compatible adapters
and normalization belong here.

`adapter = "openai"` posts `model`, `input`, `voice`, `speed`, and `response_format: "wav"`
to the complete configured endpoint, including `/v1/audio/speech`. It supports Irodori's
standard speech API and optional bearer authentication through the named API-key environment
variable. Model and voice are required; speed defaults to 1.0 and accepts 0.25 through 4.0.
Irodori-specific options, voice registration, and SSE are managed outside this adapter.

The generic HTTP and OpenAI-compatible adapters share bounded WAV download, media validation,
and normalization to 16 kHz mono PCM. Segment ordering, synthesis deadlines, and cancellation
remain in the existing playback pipeline.
