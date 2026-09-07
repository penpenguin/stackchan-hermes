"""Stable text-to-speech failure categories."""


class TtsError(RuntimeError):
    """Base TTS error exposed to turn coordination."""


class TtsTimeoutError(TtsError):
    """The configured TTS deadline elapsed."""


class TtsProviderError(TtsError):
    """A TTS provider returned a transport or media error."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
