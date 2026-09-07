"""Private Prometheus registry containing the required Bridge metrics."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


class _NoOpMetric:
    def inc(self, amount: float = 1) -> None:
        return None

    def set(self, value: float) -> None:
        return None

    def dec(self, amount: float = 1) -> None:
        return None

    def observe(self, amount: float) -> None:
        return None


class BridgeMetrics:
    """Metric handles shared by the gateway, control, and orchestration layers."""

    connected_devices: Gauge | _NoOpMetric
    websocket_connect_total: Counter | _NoOpMetric
    websocket_disconnect_total: Counter | _NoOpMetric
    websocket_auth_failure_total: Counter | _NoOpMetric
    active_turns: Gauge | _NoOpMetric
    touch_events_total: Counter | _NoOpMetric
    audio_input_frames_total: Counter | _NoOpMetric
    audio_output_frames_total: Counter | _NoOpMetric
    audio_decode_error_total: Counter | _NoOpMetric
    audio_underrun_total: Counter | _NoOpMetric
    audio_overflow_total: Counter | _NoOpMetric
    stt_duration_seconds: Histogram | _NoOpMetric
    hermes_time_to_first_delta_seconds: Histogram | _NoOpMetric
    hermes_total_duration_seconds: Histogram | _NoOpMetric
    tts_duration_seconds: Histogram | _NoOpMetric
    time_to_first_audio_seconds: Histogram | _NoOpMetric
    turn_total_duration_seconds: Histogram | _NoOpMetric
    capture_total: Counter | _NoOpMetric
    capture_failure_total: Counter | _NoOpMetric
    command_timeout_total: Counter | _NoOpMetric

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.registry = CollectorRegistry()
        if not enabled:
            no_op = _NoOpMetric()
            self.connected_devices = no_op
            self.websocket_connect_total = no_op
            self.websocket_disconnect_total = no_op
            self.websocket_auth_failure_total = no_op
            self.active_turns = no_op
            self.touch_events_total = no_op
            self.audio_input_frames_total = no_op
            self.audio_output_frames_total = no_op
            self.audio_decode_error_total = no_op
            self.audio_underrun_total = no_op
            self.audio_overflow_total = no_op
            self.stt_duration_seconds = no_op
            self.hermes_time_to_first_delta_seconds = no_op
            self.hermes_total_duration_seconds = no_op
            self.tts_duration_seconds = no_op
            self.time_to_first_audio_seconds = no_op
            self.turn_total_duration_seconds = no_op
            self.capture_total = no_op
            self.capture_failure_total = no_op
            self.command_timeout_total = no_op
            return
        self.connected_devices = Gauge(
            "connected_devices", "Currently authenticated StackChan devices", registry=self.registry
        )
        self.websocket_connect_total = Counter(
            "websocket_connect_total", "Authenticated device connections", registry=self.registry
        )
        self.websocket_disconnect_total = Counter(
            "websocket_disconnect_total", "Device WebSocket disconnections", registry=self.registry
        )
        self.websocket_auth_failure_total = Counter(
            "websocket_auth_failure_total",
            "Rejected device authentications",
            registry=self.registry,
        )
        self.active_turns = Gauge(
            "active_turns", "Currently active voice or vision turns", registry=self.registry
        )
        self.touch_events_total = Counter(
            "touch_events_total", "Accepted device touch events", registry=self.registry
        )
        self.audio_input_frames_total = Counter(
            "audio_input_frames_total", "Accepted microphone Opus frames", registry=self.registry
        )
        self.audio_output_frames_total = Counter(
            "audio_output_frames_total", "Sent playback Opus frames", registry=self.registry
        )
        self.audio_decode_error_total = Counter(
            "audio_decode_error_total", "Opus decode failures", registry=self.registry
        )
        self.audio_underrun_total = Counter(
            "audio_underrun_total", "Device playback underruns", registry=self.registry
        )
        self.audio_overflow_total = Counter(
            "audio_overflow_total", "Device playback overflows", registry=self.registry
        )
        self.stt_duration_seconds = Histogram(
            "stt_duration_seconds", "Speech-to-text duration", registry=self.registry
        )
        self.hermes_time_to_first_delta_seconds = Histogram(
            "hermes_time_to_first_delta_seconds",
            "Hermes request to first text delta",
            registry=self.registry,
        )
        self.hermes_total_duration_seconds = Histogram(
            "hermes_total_duration_seconds", "Hermes response duration", registry=self.registry
        )
        self.tts_duration_seconds = Histogram(
            "tts_duration_seconds", "Text-to-speech duration", registry=self.registry
        )
        self.time_to_first_audio_seconds = Histogram(
            "time_to_first_audio_seconds",
            "Turn start to first playback audio",
            registry=self.registry,
        )
        self.turn_total_duration_seconds = Histogram(
            "turn_total_duration_seconds", "End-to-end turn duration", registry=self.registry
        )
        self.capture_total = Counter(
            "capture_total", "Accepted capture reservations", registry=self.registry
        )
        self.capture_failure_total = Counter(
            "capture_failure_total", "Capture failures", registry=self.registry
        )
        self.command_timeout_total = Counter(
            "command_timeout_total", "Device command timeouts", registry=self.registry
        )
