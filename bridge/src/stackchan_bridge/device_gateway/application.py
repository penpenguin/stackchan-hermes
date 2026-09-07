"""FastAPI application for authenticated StackChan device connections."""

from __future__ import annotations

import builtins
import logging
from asyncio import (
    CancelledError,
    Future,
    Task,
    create_task,
    get_running_loop,
    shield,
    sleep,
    timeout,
    to_thread,
    wait_for,
)
from collections import deque
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic, time_ns
from typing import Protocol
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from python_multipart.exceptions import MultipartParseError
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from stackchan_bridge.audio.debug_store import DebugAudioStore
from stackchan_bridge.captures.store import CaptureStore, CaptureValidationError
from stackchan_bridge.motion import validate_motion_command
from stackchan_bridge.observability.metrics import BridgeMetrics
from stackchan_bridge.protocol.models import (
    MAX_AUDIO_PACKET_BYTES,
    AudioInputEndMessage,
    AudioInputStartMessage,
    CommandMessage,
    CommandResultMessage,
    ErrorMessage,
    EventMessage,
    HelloAckMessage,
    HelloMessage,
    ProtocolErrorCode,
    ProtocolMessageError,
    negotiate_protocol_version,
    parse_hello_frame,
    parse_text_frame,
)
from stackchan_bridge.security.rate_limits import TokenBucketRateLimiter
from stackchan_bridge.security.tokens import verify_device_token
from stackchan_bridge.turns.coordinator import TurnCoordinator

_LOGGER = logging.getLogger("stackchan_bridge.device_gateway")
_CAPTURE_CLEANUP_INTERVAL_SECONDS = 60.0
_CAPTURE_UPLOAD_TIMEOUT_SECONDS = 10.0
_DEBUG_AUDIO_CLEANUP_INTERVAL_SECONDS = 60.0
_INVALID_MESSAGE_WINDOW_SECONDS = 10.0
_INVALID_MESSAGE_LIMIT = 3
_AUTHENTICATION_BUCKET_KEY = "global"


@dataclass(frozen=True, slots=True)
class DeviceGatewayConfig:
    """Bounded settings needed by the first device-gateway slice."""

    device_token_hashes: Mapping[str, str] = field(default_factory=dict)
    handshake_timeout_seconds: float = 5.0
    heartbeat_interval_ms: int = 15_000
    command_timeout_ms: int = 5_000
    max_audio_packet_bytes: int = MAX_AUDIO_PACKET_BYTES
    max_seen_message_ids: int = 256
    max_connections: int = 8
    request_rate_per_second: float = 100
    request_rate_burst: int = 200
    audio_packet_rate_per_second: float = 60
    audio_packet_rate_burst: int = 100
    capture_rate_per_minute: int = 6
    capture_rate_burst: int = 2
    authentication_rate_per_second: float = 5
    authentication_rate_burst: int = 10
    max_concurrent_authentications: int = 4
    server_version: str = "0.1.0"


class AudioInputHandler(Protocol):
    """Receive an authenticated device's bounded microphone stream."""

    def set_stream_timeout_handler(
        self,
        handler: Callable[[str, AudioInputStartMessage], None],
    ) -> None: ...

    async def start(self, device_id: str, message: AudioInputStartMessage) -> None: ...

    async def frame(
        self,
        device_id: str,
        stream: AudioInputStartMessage,
        packet: bytes,
    ) -> ProtocolErrorCode | None: ...

    async def end(self, device_id: str, message: AudioInputEndMessage) -> None: ...

    async def disconnect(self, device_id: str, stream: AudioInputStartMessage) -> None: ...


class NullAudioInputHandler:
    """Discard microphone input when no turn/audio pipeline is configured."""

    def set_stream_timeout_handler(
        self,
        handler: Callable[[str, AudioInputStartMessage], None],
    ) -> None:
        return None

    async def start(self, device_id: str, message: AudioInputStartMessage) -> None:
        return None

    async def frame(
        self,
        device_id: str,
        stream: AudioInputStartMessage,
        packet: bytes,
    ) -> ProtocolErrorCode | None:
        return None

    async def end(self, device_id: str, message: AudioInputEndMessage) -> None:
        return None

    async def disconnect(self, device_id: str, stream: AudioInputStartMessage) -> None:
        return None


class DeviceEventHandler(Protocol):
    """Receive one authenticated, identity-bound physical device event."""

    async def handle(self, device_id: str, message: EventMessage) -> None: ...


class NullDeviceEventHandler:
    async def handle(self, device_id: str, message: EventMessage) -> None:
        return None


@dataclass(frozen=True, slots=True)
class _AuthenticationDecision:
    authenticated: bool = False
    rate_limited: bool = False
    retry_after_seconds: int = 0


class _AuthenticationGate:
    """Bound expensive token verification before work enters the thread pool."""

    def __init__(
        self,
        *,
        rate_per_second: float,
        capacity: int,
        max_concurrent: int,
    ) -> None:
        if max_concurrent <= 0:
            raise ValueError("authentication concurrency limit must be positive")
        self._rate_limiter = TokenBucketRateLimiter(
            rate_per_second=rate_per_second,
            capacity=capacity,
        )
        self._max_concurrent = max_concurrent
        self._active = 0
        self._lock = Lock()

    async def verify(self, token: str, encoded_hash: str) -> _AuthenticationDecision:
        with self._lock:
            rate_decision = self._rate_limiter.acquire(_AUTHENTICATION_BUCKET_KEY)
            if not rate_decision.allowed:
                return _AuthenticationDecision(
                    rate_limited=True,
                    retry_after_seconds=rate_decision.retry_after_seconds,
                )
            if self._active >= self._max_concurrent:
                return _AuthenticationDecision(rate_limited=True, retry_after_seconds=1)
            self._active += 1
        worker = create_task(to_thread(verify_device_token, token, encoded_hash))
        release_when_done = False
        try:
            authenticated = await shield(worker)
        except CancelledError:
            release_when_done = True
            worker.add_done_callback(self._release_cancelled_verification)
            raise
        finally:
            if not release_when_done:
                self._release_slot()
        return _AuthenticationDecision(authenticated=authenticated)

    def _release_cancelled_verification(self, worker: Task[bool]) -> None:
        if not worker.cancelled():
            worker.exception()
        self._release_slot()

    def _release_slot(self) -> None:
        with self._lock:
            self._active -= 1


class _CaptureMultipartParser(MultiPartParser):
    """Reject oversized file data before Starlette writes it to its spool."""

    def __init__(self, request: Request, *, max_file_bytes: int) -> None:
        super().__init__(
            request.headers,
            request.stream(),
            max_files=1,
            max_fields=0,
            max_part_size=max_file_bytes,
        )
        self._max_file_bytes = max_file_bytes
        self._current_file_bytes = 0
        self._uploads: list[UploadFile] = []

    def on_headers_finished(self) -> None:
        super().on_headers_finished()
        if self._current_part.file is not None:
            self._uploads.append(self._current_part.file)

    async def close(self) -> None:
        for upload in self._uploads:
            await upload.close()

    def on_part_begin(self) -> None:
        super().on_part_begin()
        self._current_file_bytes = 0

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._current_part.file is not None:
            incoming_bytes = end - start
            if self._current_file_bytes + incoming_bytes > self._max_file_bytes:
                raise CaptureValidationError(
                    "CAPTURE_TOO_LARGE",
                    "capture exceeds the configured limit",
                )
            self._current_file_bytes += incoming_bytes
        super().on_part_data(data, start, end)


async def _read_capture_upload(request: Request, *, max_bytes: int) -> tuple[str, bytes]:
    parser = _CaptureMultipartParser(request, max_file_bytes=max_bytes)
    try:
        async with timeout(_CAPTURE_UPLOAD_TIMEOUT_SECONDS):
            form = await parser.parse()
            upload = form.get("file")
            if not isinstance(upload, UploadFile):
                raise CaptureValidationError("INVALID_UPLOAD", "multipart file field is required")
            body = bytearray()
            while chunk := await upload.read(65_536):
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise CaptureValidationError(
                        "CAPTURE_TOO_LARGE",
                        "capture exceeds the configured limit",
                    )
            return upload.content_type or "", bytes(body)
    finally:
        await parser.close()


@dataclass(frozen=True, slots=True)
class DeviceConnection:
    """One authenticated, negotiated device connection."""

    connection_id: UUID
    device_id: str
    hello: HelloMessage
    websocket: WebSocket
    protocol_version: int = 1
    pending_commands: dict[UUID, Future[CommandResultMessage]] = field(
        default_factory=dict,
        compare=False,
        repr=False,
    )


class DeviceNotConnectedError(RuntimeError):
    """A command targeted a device without a live connection."""


class CommandTimedOutError(RuntimeError):
    """Firmware didn't return a command result before the deadline."""


class CommandQueueFullError(RuntimeError):
    """A device already has the maximum number of commands awaiting results."""


class DeviceDisconnectedError(RuntimeError):
    """A pending command lost ownership when its device disconnected."""


class DeviceConnectionLimitError(RuntimeError):
    """A distinct device exceeded the configured registry capacity."""


class DeviceCapabilityError(RuntimeError):
    """A command targeted physical hardware the device did not advertise."""

    def __init__(self, capability: str) -> None:
        super().__init__(f"device capability is unavailable: {capability}")
        self.capability = capability


class DeviceRegistry:
    """In-memory live-device registry where a newer connection wins."""

    def __init__(
        self,
        *,
        command_timeout_seconds: float,
        metrics: BridgeMetrics | None = None,
        max_connections: int = 8,
    ) -> None:
        if max_connections <= 0:
            raise ValueError("device connection limit must be positive")
        self._connections: dict[str, DeviceConnection] = {}
        self._pending_handshakes: set[UUID] = set()
        self._command_timeout_seconds = command_timeout_seconds
        self._max_connections = max_connections
        self.metrics = metrics or BridgeMetrics()

    async def register(self, connection: DeviceConnection, *, ready: bool = True) -> None:
        previous = self._connections.get(connection.device_id)
        if previous is None and len(self._connections) >= self._max_connections:
            raise DeviceConnectionLimitError("device connection limit reached")
        self._connections[connection.device_id] = connection
        if previous is not None:
            self._pending_handshakes.discard(previous.connection_id)
        if not ready:
            self._pending_handshakes.add(connection.connection_id)
        self.metrics.websocket_connect_total.inc()
        self.metrics.connected_devices.set(len(self.connected_device_ids()))
        _LOGGER.info(
            "device connected",
            extra={
                "component": "device_gateway",
                "event": "device.connected",
                "device_id": connection.device_id,
                "connection_id": str(connection.connection_id),
            },
        )
        if previous is not None and previous.connection_id != connection.connection_id:
            self._fail_pending(previous, DeviceDisconnectedError("connection replaced"))
            try:
                await previous.websocket.close(code=4409, reason="connection replaced")
            except Exception:
                _LOGGER.warning(
                    "replaced device connection was already closed",
                    exc_info=True,
                    extra={
                        "component": "device_gateway",
                        "event": "device.replaced_close_failed",
                        "device_id": previous.device_id,
                        "connection_id": str(previous.connection_id),
                    },
                )

    def mark_ready(self, device_id: str, connection_id: UUID) -> bool:
        """Publish an owned connection only after its hello acknowledgement was sent."""

        current = self._connections.get(device_id)
        if current is None or current.connection_id != connection_id:
            return False
        self._pending_handshakes.discard(connection_id)
        self.metrics.connected_devices.set(len(self.connected_device_ids()))
        return True

    def unregister(self, device_id: str, connection_id: UUID) -> None:
        current = self._connections.get(device_id)
        if current is not None and current.connection_id == connection_id:
            del self._connections[device_id]
            self._pending_handshakes.discard(connection_id)
            self._fail_pending(current, DeviceDisconnectedError("device disconnected"))
            self.metrics.websocket_disconnect_total.inc()
            self.metrics.connected_devices.set(len(self.connected_device_ids()))
            _LOGGER.info(
                "device disconnected",
                extra={
                    "component": "device_gateway",
                    "event": "device.disconnected",
                    "device_id": device_id,
                    "connection_id": str(connection_id),
                },
            )

    def connected_device_ids(self) -> tuple[str, ...]:
        return tuple(connection.device_id for connection in self.connected_devices())

    def connected_devices(self) -> tuple[DeviceConnection, ...]:
        """Return a stable snapshot of live connection records."""

        return tuple(
            connection
            for key in sorted(self._connections)
            if (connection := self.get_connection(key)) is not None
        )

    def get_connection(
        self, device_id: str, *, include_pending: bool = False
    ) -> DeviceConnection | None:
        connection = self._connections.get(device_id)
        if (
            connection is not None
            and not include_pending
            and connection.connection_id in self._pending_handshakes
        ):
            return None
        return connection

    async def send_command(
        self,
        device_id: str,
        name: str,
        args: Mapping[str, object],
        *,
        turn_id: UUID | None = None,
    ) -> CommandResultMessage:
        """Send one typed command and await its correlated result."""

        connection = self.get_connection(device_id)
        if connection is None:
            raise DeviceNotConnectedError(f"device is not connected: {device_id}")
        missing_capability = _missing_command_capability(connection, name)
        if missing_capability is not None:
            raise DeviceCapabilityError(missing_capability)
        if len(connection.pending_commands) >= 16:
            raise CommandQueueFullError("device has too many pending commands")
        request_id = uuid4()
        command_data: dict[str, object] = {
            "v": 1,
            "type": "command",
            "message_id": str(uuid4()),
            "request_id": str(request_id),
            "sent_at_ms": time_ns() // 1_000_000,
            "payload": {"name": name, "args": dict(args)},
        }
        if turn_id is not None:
            command_data["turn_id"] = str(turn_id)
        command = CommandMessage.model_validate(command_data)
        if command.payload.name in {"head.set_angles", "head.home"}:
            validate_motion_command(
                connection.hello.payload.hardware_model,
                command.payload,
            )
        result_future: Future[CommandResultMessage] = get_running_loop().create_future()
        connection.pending_commands[request_id] = result_future
        try:
            try:
                await connection.websocket.send_text(command.model_dump_json(exclude_none=True))
            except (RuntimeError, WebSocketDisconnect) as error:
                raise DeviceDisconnectedError(
                    "device disconnected while sending command"
                ) from error
            if self._connections.get(device_id) is not connection:
                if result_future.done() and not result_future.cancelled():
                    result_future.exception()
                raise DeviceDisconnectedError("command connection was replaced or disconnected")
            try:
                return await wait_for(result_future, timeout=self._command_timeout_seconds)
            except builtins.TimeoutError as error:
                self.metrics.command_timeout_total.inc()
                raise CommandTimedOutError(f"command timed out: {request_id}") from error
        finally:
            connection.pending_commands.pop(request_id, None)

    def route_result(
        self,
        device_id: str,
        connection_id: UUID,
        result: CommandResultMessage,
    ) -> bool:
        """Resolve an owned pending command, rejecting stale connection results."""

        connection = self._connections.get(device_id)
        if connection is None or connection.connection_id != connection_id:
            return False
        pending = connection.pending_commands.get(result.request_id)
        if pending is None or pending.done():
            return False
        pending.set_result(result)
        return True

    @staticmethod
    def _fail_pending(connection: DeviceConnection, error: Exception) -> None:
        for pending in connection.pending_commands.values():
            if not pending.done():
                pending.set_exception(error)


def _missing_command_capability(connection: DeviceConnection, command_name: str) -> str | None:
    capabilities = connection.hello.payload.capabilities
    required_by_prefix = (
        ("camera.", "camera", capabilities.camera),
        ("head.", "head", capabilities.head),
        ("avatar.", "avatar", capabilities.avatar),
        ("display.", "display", capabilities.display),
        ("audio.", "speaker", capabilities.speaker),
        ("led.", "led", capabilities.led_count > 0),
    )
    for prefix, capability, available in required_by_prefix:
        if command_name.startswith(prefix) and not available:
            return capability
    return None


def create_device_gateway_app(
    config: DeviceGatewayConfig,
    *,
    metrics: BridgeMetrics | None = None,
    capture_store: CaptureStore | None = None,
    debug_audio_store: DebugAudioStore | None = None,
    audio_input_handler: AudioInputHandler | None = None,
    event_handler: DeviceEventHandler | None = None,
    registry: DeviceRegistry | None = None,
    turn_coordinator: TurnCoordinator | None = None,
) -> FastAPI:
    """Create the device-facing ASGI application without external side effects."""

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        cleanup_tasks: list[Task[None]] = []
        if capture_store is not None:
            cleanup_tasks.append(create_task(_purge_captures_periodically(capture_store)))
        if debug_audio_store is not None and debug_audio_store.enabled:
            cleanup_tasks.append(create_task(_purge_debug_audio_periodically(debug_audio_store)))
        try:
            yield
        finally:
            for task in cleanup_tasks:
                task.cancel()
            for task in cleanup_tasks:
                with suppress(CancelledError):
                    await task

    app = FastAPI(
        title="StackChan Device Gateway",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    if registry is None:
        registry = DeviceRegistry(
            command_timeout_seconds=config.command_timeout_ms / 1_000,
            metrics=metrics,
            max_connections=config.max_connections,
        )
    app.state.device_registry = registry
    app.state.gateway_config = config
    app.state.metrics = registry.metrics
    app.state.capture_store = capture_store
    selected_audio_handler = audio_input_handler or NullAudioInputHandler()
    selected_event_handler = event_handler or NullDeviceEventHandler()
    app.state.audio_input_handler = selected_audio_handler
    app.state.event_handler = selected_event_handler
    active_audio_inputs: dict[UUID, AudioInputStartMessage] = {}
    timed_out_audio_inputs: dict[UUID, AudioInputStartMessage] = {}

    def release_timed_out_stream(
        device_id: str,
        stream: AudioInputStartMessage,
    ) -> None:
        connection = registry.get_connection(device_id)
        if connection is None:
            return
        active = active_audio_inputs.get(connection.connection_id)
        if (
            active is None
            or active.stream_id != stream.stream_id
            or active.turn_id != stream.turn_id
        ):
            return
        active_audio_inputs.pop(connection.connection_id, None)
        timed_out_audio_inputs[connection.connection_id] = stream

    selected_audio_handler.set_stream_timeout_handler(release_timed_out_stream)
    authentication_gate = _AuthenticationGate(
        rate_per_second=config.authentication_rate_per_second,
        capacity=config.authentication_rate_burst,
        max_concurrent=config.max_concurrent_authentications,
    )
    capture_rate_limiter = TokenBucketRateLimiter(
        rate_per_second=config.capture_rate_per_minute / 60,
        capacity=config.capture_rate_burst,
    )

    @app.post("/v1/device/captures/{capture_id}")
    async def upload_capture(capture_id: UUID, request: Request) -> JSONResponse:
        device_id, auth_error = await _authenticate_http_device(
            request,
            config,
            registry.metrics,
            authentication_gate,
        )
        if auth_error is not None:
            return auth_error
        rate_decision = capture_rate_limiter.acquire(device_id)
        if not rate_decision.allowed:
            registry.metrics.capture_failure_total.inc()
            response = _http_error(
                429,
                "CAPTURE_RATE_LIMITED",
                "capture upload rate limit exceeded",
            )
            response.headers["Retry-After"] = str(rate_decision.retry_after_seconds)
            return response
        if capture_store is None:
            return _http_error(503, "CAPTURE_STORE_UNAVAILABLE", "capture store is unavailable")
        try:
            content_type, body = await _read_capture_upload(
                request, max_bytes=capture_store.max_bytes
            )
            record = capture_store.save(
                capture_id,
                device_id=device_id,
                content_type=content_type,
                body=body,
            )
        except builtins.TimeoutError:
            registry.metrics.capture_failure_total.inc()
            return _http_error(408, "CAPTURE_UPLOAD_TIMEOUT", "capture upload timed out")
        except CaptureValidationError as error:
            registry.metrics.capture_failure_total.inc()
            return _http_error(_capture_error_status(error.code), error.code, str(error))
        except (KeyError, MultiPartException, MultipartParseError):
            registry.metrics.capture_failure_total.inc()
            return _http_error(422, "INVALID_UPLOAD", "malformed multipart body")
        registry.metrics.capture_total.inc()
        return JSONResponse(
            status_code=201,
            content={
                "capture_id": str(record.capture_id),
                "mime_type": record.content_type,
                "width": record.width,
                "height": record.height,
                "size_bytes": record.size_bytes,
                "sha256": record.sha256,
                "expires_at": record.expires_at,
            },
        )

    @app.websocket("/v1/device/ws")
    async def device_websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        device_id = websocket.headers.get("X-StackChan-Device-Id", "")
        encoded_hash = config.device_token_hashes.get(device_id)
        if encoded_hash is None:
            registry.metrics.websocket_auth_failure_total.inc()
            await websocket.close(code=4403, reason="unknown device")
            return
        authorization = websocket.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if scheme != "Bearer" or separator != " " or not token:
            registry.metrics.websocket_auth_failure_total.inc()
            await websocket.close(code=4401, reason="unauthorized")
            return
        authentication_decision = await authentication_gate.verify(token, encoded_hash)
        if authentication_decision.rate_limited:
            registry.metrics.websocket_auth_failure_total.inc()
            await websocket.close(code=4429, reason="authentication rate limit exceeded")
            return
        if not authentication_decision.authenticated:
            registry.metrics.websocket_auth_failure_total.inc()
            await websocket.close(code=4401, reason="unauthorized")
            return

        try:
            async with timeout(config.handshake_timeout_seconds):
                hello = parse_hello_frame(await websocket.receive_text())
            selected_version = negotiate_protocol_version(
                hello,
                authenticated_device_id=device_id,
            )
        except builtins.TimeoutError:
            await websocket.close(code=4408, reason="hello timeout")
            return
        except WebSocketDisconnect:
            return
        except ProtocolMessageError as error:
            await websocket.close(code=_close_code(error.code), reason=str(error)[:123])
            return

        connection_id = uuid4()
        connection = DeviceConnection(
            connection_id=connection_id,
            device_id=device_id,
            hello=hello,
            websocket=websocket,
            protocol_version=selected_version,
        )
        previous_connection = registry.get_connection(device_id, include_pending=True)
        try:
            await registry.register(connection, ready=False)
        except DeviceConnectionLimitError:
            await websocket.close(code=4429, reason="device connection limit reached")
            return
        seen_message_ids: set[UUID] = set()
        seen_message_order: deque[UUID] = deque()
        invalid_message_times: deque[float] = deque()
        request_rate_limiter = TokenBucketRateLimiter(
            rate_per_second=config.request_rate_per_second,
            capacity=config.request_rate_burst,
        )
        audio_packet_rate_limiter = TokenBucketRateLimiter(
            rate_per_second=config.audio_packet_rate_per_second,
            capacity=config.audio_packet_rate_burst,
        )

        async def report_invalid_message(error: ProtocolMessageError) -> bool:
            now = monotonic()
            while (
                invalid_message_times
                and now - invalid_message_times[0] >= _INVALID_MESSAGE_WINDOW_SECONDS
            ):
                invalid_message_times.popleft()
            invalid_message_times.append(now)
            if len(invalid_message_times) >= _INVALID_MESSAGE_LIMIT:
                await websocket.close(
                    code=_close_code(error.code),
                    reason=str(error)[:123],
                )
                return True
            response = _invalid_message_response(error.code)
            await websocket.send_text(response.model_dump_json(exclude_none=True))
            return False

        try:
            if (
                previous_connection is not None
                and previous_connection is not connection
                and turn_coordinator is not None
            ):
                active_turn = turn_coordinator.current(device_id)
                if active_turn is not None:
                    await turn_coordinator.cancel_turn(
                        device_id,
                        active_turn.turn_id,
                        reason="connection_replaced",
                    )
            if previous_connection is not None and previous_connection is not connection:
                timed_out_audio_inputs.pop(previous_connection.connection_id, None)
                previous_input = active_audio_inputs.pop(
                    previous_connection.connection_id,
                    None,
                )
                if previous_input is not None:
                    await selected_audio_handler.disconnect(device_id, previous_input)
            acknowledgement = HelloAckMessage.model_validate(
                {
                    "v": 1,
                    "type": "hello_ack",
                    "message_id": str(uuid4()),
                    "sent_at_ms": time_ns() // 1_000_000,
                    "payload": {
                        "connection_id": connection_id,
                        "selected_protocol_version": selected_version,
                        "heartbeat_interval_ms": config.heartbeat_interval_ms,
                        "max_command_timeout_ms": config.command_timeout_ms,
                        "server_version": config.server_version,
                    },
                }
            )
            await websocket.send_text(acknowledgement.model_dump_json())
            if not registry.mark_ready(device_id, connection_id):
                await websocket.close(code=4409, reason="connection replaced during handshake")
                return

            while True:
                incoming = await websocket.receive()
                if incoming["type"] == "websocket.disconnect":
                    break
                binary_frame = incoming.get("bytes")
                if binary_frame is not None:
                    if not audio_packet_rate_limiter.acquire(str(connection_id)).allowed:
                        await websocket.close(code=4429, reason="audio packet rate limit exceeded")
                        break
                    if len(binary_frame) > config.max_audio_packet_bytes:
                        await websocket.close(code=4400, reason="audio packet too large")
                        break
                    active_input = active_audio_inputs.get(connection_id)
                    if active_input is None:
                        closed = await report_invalid_message(
                            ProtocolMessageError(
                                ProtocolErrorCode.INVALID_STATE,
                                "audio frame received outside an input stream",
                            )
                        )
                        if closed:
                            break
                        continue
                    stream_error = await selected_audio_handler.frame(
                        device_id,
                        active_input,
                        binary_frame,
                    )
                    registry.metrics.audio_input_frames_total.inc()
                    if stream_error is not None:
                        failed_input = active_input
                        active_audio_inputs.pop(connection_id, None)
                        response = _audio_input_error_response(stream_error, failed_input)
                        await websocket.send_text(response.model_dump_json(exclude_none=True))
                    continue
                if not request_rate_limiter.acquire(str(connection_id)).allowed:
                    await websocket.close(code=4429, reason="request rate limit exceeded")
                    break
                text_frame = incoming.get("text")
                if text_frame is not None:
                    try:
                        message = parse_text_frame(text_frame)
                    except ProtocolMessageError as error:
                        if await report_invalid_message(error):
                            break
                        continue
                    if message.message_id in seen_message_ids:
                        continue
                    seen_message_ids.add(message.message_id)
                    seen_message_order.append(message.message_id)
                    if len(seen_message_order) > config.max_seen_message_ids:
                        seen_message_ids.remove(seen_message_order.popleft())
                    if isinstance(message, CommandResultMessage):
                        registry.route_result(device_id, connection_id, message)
                    elif isinstance(message, AudioInputStartMessage):
                        active_input = active_audio_inputs.get(connection_id)
                        if active_input is not None or not _audio_format_matches_hello(
                            message, hello
                        ):
                            if await report_invalid_message(
                                ProtocolMessageError(
                                    ProtocolErrorCode.INVALID_STATE,
                                    "invalid audio input start state",
                                )
                            ):
                                break
                            continue
                        active_audio_inputs[connection_id] = message
                        await selected_audio_handler.start(device_id, message)
                    elif isinstance(message, AudioInputEndMessage):
                        active_input = active_audio_inputs.get(connection_id)
                        if (
                            active_input is not None
                            and message.stream_id == active_input.stream_id
                            and message.turn_id == active_input.turn_id
                        ):
                            active_audio_inputs.pop(connection_id, None)
                            await selected_audio_handler.end(device_id, message)
                            continue
                        timed_out_input = timed_out_audio_inputs.get(connection_id)
                        if (
                            timed_out_input is not None
                            and message.stream_id == timed_out_input.stream_id
                            and message.turn_id == timed_out_input.turn_id
                        ):
                            timed_out_audio_inputs.pop(connection_id, None)
                            continue
                        if await report_invalid_message(
                            ProtocolMessageError(
                                ProtocolErrorCode.INVALID_STATE,
                                "audio input end does not match the active stream",
                            )
                        ):
                            break
                    elif isinstance(message, EventMessage):
                        if message.device_id != device_id:
                            await websocket.close(
                                code=4403, reason="event device identity mismatch"
                            )
                            break
                        if message.payload.name == "audio.underrun":
                            registry.metrics.audio_underrun_total.inc()
                        elif message.payload.name == "audio.overflow":
                            registry.metrics.audio_overflow_total.inc()
                        await selected_event_handler.handle(device_id, message)
                    elif isinstance(message, ErrorMessage):
                        _LOGGER.warning(
                            "device reported a protocol error",
                            extra={
                                "component": "device_gateway",
                                "event": "device.protocol_error",
                                "device_id": device_id,
                                "error_code": message.payload.code.value,
                                "turn_id": str(message.turn_id) if message.turn_id else None,
                                "stream_id": str(message.stream_id) if message.stream_id else None,
                                "request_id": str(message.request_id)
                                if message.request_id
                                else None,
                            },
                        )
                    else:
                        await websocket.close(code=4400, reason="unexpected device message")
                        break
        except (WebSocketDisconnect, RuntimeError):
            pass
        except ProtocolMessageError as error:
            await websocket.close(code=_close_code(error.code), reason=str(error)[:123])
        finally:
            try:
                timed_out_audio_inputs.pop(connection_id, None)
                owned_input = active_audio_inputs.pop(connection_id, None)
                if owned_input is not None:
                    await selected_audio_handler.disconnect(device_id, owned_input)
            finally:
                try:
                    coordinator = turn_coordinator
                    active_turn = (
                        coordinator.current(device_id)
                        if coordinator is not None
                        and registry.get_connection(device_id, include_pending=True) is connection
                        else None
                    )
                    if coordinator is not None and active_turn is not None:
                        await coordinator.cancel_turn(
                            device_id,
                            active_turn.turn_id,
                            reason="disconnect",
                        )
                finally:
                    registry.unregister(device_id, connection_id)

    return app


async def _purge_debug_audio_periodically(store: DebugAudioStore) -> None:
    interval = min(_DEBUG_AUDIO_CLEANUP_INTERVAL_SECONDS, float(store.ttl_seconds))
    while True:
        await sleep(interval)
        try:
            store.purge_expired()
        except OSError:
            _LOGGER.exception(
                "failed to purge expired debug audio",
                extra={"component": "audio", "event": "audio.debug_purge_failed"},
            )


async def _purge_captures_periodically(capture_store: CaptureStore) -> None:
    interval_seconds = min(
        _CAPTURE_CLEANUP_INTERVAL_SECONDS,
        float(capture_store.ttl_seconds),
    )
    while True:
        await sleep(interval_seconds)
        try:
            capture_store.purge_expired()
        except OSError:
            _LOGGER.exception(
                "failed to purge expired captures",
                extra={"component": "captures", "event": "capture.purge_failed"},
            )


def _close_code(error_code: ProtocolErrorCode) -> int:
    if error_code is ProtocolErrorCode.UNSUPPORTED_VERSION:
        return 4410
    if error_code is ProtocolErrorCode.UNKNOWN_DEVICE:
        return 4403
    return 4400


def _invalid_message_response(error_code: ProtocolErrorCode) -> ErrorMessage:
    return ErrorMessage.model_validate(
        {
            "v": 1,
            "type": "error",
            "message_id": str(uuid4()),
            "sent_at_ms": time_ns() // 1_000_000,
            "payload": {
                "code": error_code.value,
                "message": "invalid protocol message",
            },
        }
    )


def _audio_input_error_response(
    error_code: ProtocolErrorCode,
    stream: AudioInputStartMessage,
) -> ErrorMessage:
    return ErrorMessage.model_validate(
        {
            "v": 1,
            "type": "error",
            "message_id": str(uuid4()),
            "turn_id": str(stream.turn_id),
            "stream_id": str(stream.stream_id),
            "sent_at_ms": time_ns() // 1_000_000,
            "payload": {
                "code": error_code.value,
                "message": "audio input stream ended after repeated decode failures",
            },
        }
    )


def _audio_format_matches_hello(
    message: AudioInputStartMessage,
    hello: HelloMessage,
) -> bool:
    return (
        message.payload.codec == hello.payload.audio.codec
        and message.payload.sample_rate == hello.payload.audio.sample_rate
        and message.payload.channels == hello.payload.audio.channels
        and message.payload.frame_ms == hello.payload.audio.frame_ms
    )


async def _authenticate_http_device(
    request: Request,
    config: DeviceGatewayConfig,
    metrics: BridgeMetrics,
    authentication_gate: _AuthenticationGate,
) -> tuple[str, JSONResponse | None]:
    device_id = request.headers.get("X-StackChan-Device-Id", "")
    encoded_hash = config.device_token_hashes.get(device_id)
    if encoded_hash is None:
        metrics.websocket_auth_failure_total.inc()
        return "", _http_error(403, "UNKNOWN_DEVICE", "unknown device")
    authorization = request.headers.get("Authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if scheme != "Bearer" or separator != " " or not token:
        metrics.websocket_auth_failure_total.inc()
        return "", _http_error(401, "UNAUTHORIZED", "unauthorized")
    authentication_decision = await authentication_gate.verify(token, encoded_hash)
    if authentication_decision.rate_limited:
        metrics.websocket_auth_failure_total.inc()
        response = _http_error(
            429,
            "AUTHENTICATION_RATE_LIMITED",
            "authentication rate limit exceeded",
        )
        response.headers["Retry-After"] = str(authentication_decision.retry_after_seconds)
        return "", response
    if not authentication_decision.authenticated:
        metrics.websocket_auth_failure_total.inc()
        return "", _http_error(401, "UNAUTHORIZED", "unauthorized")
    return device_id, None


def _capture_error_status(code: str) -> int:
    return {
        "CAPTURE_NOT_FOUND": 404,
        "CAPTURE_EXPIRED": 410,
        "CAPTURE_OWNERSHIP": 403,
        "CAPTURE_TOO_LARGE": 413,
    }.get(code, 422)


def _http_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )
