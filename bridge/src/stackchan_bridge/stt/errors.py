"""Stable STT failure categories."""


class SttError(RuntimeError):
    """Base error exposed to the turn coordinator."""


class SttTimeoutError(SttError):
    """The configured STT deadline elapsed."""


class SttProviderError(SttError):
    """An STT provider returned a transport or response error."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
