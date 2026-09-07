"""Stable Hermes public API failure categories."""


class HermesError(RuntimeError):
    """Base error visible to readiness and turn coordination."""


class HermesAuthenticationError(HermesError):
    """Hermes rejected the configured API key."""


class HermesEndpointError(HermesError):
    """A configured public endpoint or profile path was not found."""


class HermesRateLimitError(HermesError):
    """Hermes or its provider rate-limited the request."""


class HermesServerError(HermesError):
    """Hermes returned a server-side failure."""


class HermesProtocolError(HermesError):
    """Hermes returned malformed or incomplete SSE/JSON."""


class HermesResponseError(HermesError):
    """Hermes emitted a typed error inside an otherwise successful SSE response."""

    def __init__(self, code: str) -> None:
        super().__init__("Hermes response failed")
        self.code = code


class HermesTransportError(HermesError):
    """Hermes could not be reached or timed out."""


class HermesTimeoutError(HermesTransportError):
    """Hermes did not respond within the configured deadline."""
