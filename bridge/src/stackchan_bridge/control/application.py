"""Loopback Control API backed by the live device registry."""

from __future__ import annotations

from asyncio import gather
from collections.abc import Awaitable, Callable, Mapping
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, ValidationError

from stackchan_bridge.captures.coordinator import (
    CaptureCommandFailedError,
    CaptureCoordinator,
    CaptureTimedOutError,
)
from stackchan_bridge.captures.store import CaptureStore
from stackchan_bridge.device_gateway.application import (
    CommandQueueFullError,
    CommandTimedOutError,
    DeviceCapabilityError,
    DeviceConnection,
    DeviceDisconnectedError,
    DeviceNotConnectedError,
    DeviceRegistry,
)
from stackchan_bridge.hermes.errors import HermesError
from stackchan_bridge.motion import MotionSafetyError
from stackchan_bridge.observability.metrics import BridgeMetrics
from stackchan_bridge.protocol.models import DeviceId, EventPayload
from stackchan_bridge.speech_models import SpeechRequest, SpeechStatus
from stackchan_bridge.tts.errors import TtsError
from stackchan_bridge.turns.coordinator import (
    StaleTurnError,
    Turn,
    TurnBusyError,
    TurnCoordinator,
    TurnState,
)
from stackchan_bridge.turns.service import VoiceTurnError
from stackchan_bridge.turns.speech import SpeechNotFoundError, SpeechUnavailableError

ReadinessProbe = Callable[[], Awaitable[bool]]


class VisionTurnRunner(Protocol):
    async def run(self, device_id: str, *, question: str, quality: int = 80) -> Turn: ...


class SpeechTurnRunner(Protocol):
    async def start(self, device_id: str, *, text: str) -> SpeechStatus: ...

    def get(self, device_id: str, turn_id: UUID) -> SpeechStatus: ...


class ConversationResetter(Protocol):
    def reset_conversation(self, device_id: str) -> str: ...


class TouchStateReader(Protocol):
    def last_touch(self, device_id: str) -> EventPayload | None: ...


class DeviceView(BaseModel):
    """Safe device metadata suitable for local API and MCP callers."""

    model_config = ConfigDict(extra="forbid", strict=True)

    device_id: str
    connected: bool
    device_name: str
    firmware_version: str
    hardware_model: str
    protocol_version: int
    capabilities: dict[str, bool | int]


class DeviceListResponse(BaseModel):
    devices: list[DeviceView]


class CommandRequest(BaseModel):
    """A local caller's typed protocol command request."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    args: dict[str, JsonValue]
    turn_id: Annotated[UUID, Field(strict=False)] | None = None


class CancelSpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    turn_id: Annotated[UUID, Field(strict=False)]


class CaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    quality: Annotated[int, Field(ge=10, le=95)] = 80


class VisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000),
    ]
    quality: Annotated[int, Field(ge=10, le=95)] = 80


def create_control_app(
    registry: DeviceRegistry,
    *,
    readiness_checks: Mapping[str, ReadinessProbe] | None = None,
    metrics: BridgeMetrics | None = None,
    capture_store: CaptureStore | None = None,
    capture_coordinator: CaptureCoordinator | None = None,
    turn_coordinator: TurnCoordinator | None = None,
    vision_turn_service: VisionTurnRunner | None = None,
    speech_turn_service: SpeechTurnRunner | None = None,
    conversation_resetter: ConversationResetter | None = None,
    touch_state: TouchStateReader | None = None,
) -> FastAPI:
    """Create an app intended to be served only on the configured loopback bind."""

    app = FastAPI(title="StackChan Control API", docs_url=None, redoc_url=None)
    probes = dict(readiness_checks or {"configuration": _not_configured})
    selected_metrics = metrics or registry.metrics
    app.state.capture_store = capture_store
    app.state.capture_coordinator = capture_coordinator
    app.state.turn_coordinator = turn_coordinator
    app.state.vision_turn_service = vision_turn_service
    app.state.speech_turn_service = speech_turn_service
    app.state.conversation_resetter = conversation_resetter
    app.state.touch_state = touch_state
    app.state.device_registry = registry
    app.state.metrics = selected_metrics

    @app.exception_handler(CommandQueueFullError)
    async def command_queue_full(_request: Request, _error: CommandQueueFullError) -> JSONResponse:
        return _error_response(429, "COMMAND_QUEUE_FULL", "device command queue is full")

    @app.get("/v1/control/captures/{capture_id}")
    async def get_capture(capture_id: UUID) -> Response:
        if capture_store is None:
            return _error_response(
                503,
                "CAPTURE_STORE_UNAVAILABLE",
                "capture store is unavailable",
            )
        record = capture_store.get(capture_id)
        if record is None or not record.path.is_file():
            return _error_response(404, "CAPTURE_NOT_FOUND", "capture was not found")
        return Response(
            content=record.path.read_bytes(),
            media_type=record.content_type,
            headers={"Cache-Control": "no-store"},
        )

    @app.delete("/v1/control/captures/{capture_id}", status_code=204)
    async def delete_capture(capture_id: UUID) -> Response:
        if capture_store is None:
            return _error_response(
                503,
                "CAPTURE_STORE_UNAVAILABLE",
                "capture store is unavailable",
            )
        if not capture_store.delete(capture_id):
            return _error_response(404, "CAPTURE_NOT_FOUND", "capture was not found")
        return Response(status_code=204)

    @app.post("/v1/control/devices/{device_id}/captures", status_code=201)
    async def initiate_capture(device_id: str, request: CaptureRequest) -> JSONResponse:
        if capture_coordinator is None:
            return _error_response(
                503,
                "CAPTURE_UNAVAILABLE",
                "capture coordination is unavailable",
            )
        try:
            record = await capture_coordinator.take_photo(device_id, quality=request.quality)
        except DeviceNotConnectedError:
            return _error_response(
                404,
                "DEVICE_NOT_CONNECTED",
                f"device is not connected: {device_id}",
            )
        except DeviceCapabilityError as error:
            return _capability_error_response(error)
        except CaptureTimedOutError as error:
            return _error_response(
                504, error.code, "capture deadline expired", details=error.details
            )
        except CaptureCommandFailedError as error:
            return _capture_error_response(error)
        except DeviceDisconnectedError:
            return _error_response(409, "CAPTURE_FAILED", "device capture failed")
        except CommandTimedOutError:
            return _error_response(504, "COMMAND_TIMEOUT", "camera command timed out")
        return JSONResponse(
            status_code=201,
            content={
                "capture_id": str(record.capture_id),
                "mime_type": record.content_type,
                "width": record.width,
                "height": record.height,
                "size_bytes": record.size_bytes,
                "sha256": record.sha256,
                "local_url": f"/v1/control/captures/{record.capture_id}",
                "expires_at": record.expires_at,
            },
        )

    @app.post("/v1/control/devices/{device_id}/vision")
    async def start_vision_turn(device_id: str, request: VisionRequest) -> JSONResponse:
        if vision_turn_service is None:
            return _error_response(
                503,
                "VISION_UNAVAILABLE",
                "vision turn service is unavailable",
            )
        try:
            turn = await vision_turn_service.run(
                device_id,
                question=request.question,
                quality=request.quality,
            )
        except TurnBusyError:
            return _error_response(409, "TURN_BUSY", "device already has an active turn")
        except DeviceNotConnectedError:
            return _error_response(
                404,
                "DEVICE_NOT_CONNECTED",
                f"device is not connected: {device_id}",
            )
        except DeviceCapabilityError as error:
            return _capability_error_response(error)
        except CaptureTimedOutError as error:
            return _error_response(
                504, error.code, "capture deadline expired", details=error.details
            )
        except CaptureCommandFailedError as error:
            return _capture_error_response(error)
        except DeviceDisconnectedError:
            return _error_response(409, "CAPTURE_FAILED", "device capture failed")
        except CommandTimedOutError:
            return _error_response(504, "COMMAND_TIMEOUT", "camera command timed out")
        except StaleTurnError:
            return _error_response(409, "TURN_CANCELLED", "vision turn was cancelled")
        except HermesError:
            return _error_response(502, "HERMES_FAILED", "Hermes vision request failed")
        except TtsError:
            return _error_response(502, "TTS_FAILED", "vision speech synthesis failed")
        except VoiceTurnError:
            return _error_response(502, "VISION_RESPONSE_FAILED", "vision response failed")
        return JSONResponse(
            content={
                "turn_id": str(turn.turn_id),
                "state": turn.state.value,
                "capture_id": str(turn.capture_id) if turn.capture_id is not None else None,
                "hermes_response_id": turn.hermes_response_id,
                "output_stream_ids": [str(stream_id) for stream_id in turn.output_stream_ids],
            }
        )

    @app.post("/v1/control/devices/{device_id}/conversation/reset")
    async def reset_conversation(device_id: str) -> JSONResponse:
        if conversation_resetter is None:
            return _error_response(
                503,
                "CONVERSATION_RESET_UNAVAILABLE",
                "conversation reset is unavailable",
            )
        try:
            conversation = conversation_resetter.reset_conversation(device_id)
        except (ValidationError, ValueError):
            return _error_response(422, "INVALID_DEVICE_ID", "device id is invalid")
        return JSONResponse(content={"conversation": conversation})

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/health/ready")
    async def ready() -> JSONResponse:
        names = sorted(probes)
        outcomes = await gather(*(probes[name]() for name in names), return_exceptions=True)
        checks = {name: outcome is True for name, outcome in zip(names, outcomes, strict=True)}
        is_ready = all(checks.values())
        return JSONResponse(
            status_code=200 if is_ready else 503,
            content={
                "ready": is_ready,
                "connected_devices": len(registry.connected_device_ids()),
                "checks": checks,
            },
        )

    if selected_metrics.enabled:

        @app.get("/metrics")
        async def prometheus_metrics() -> Response:
            return Response(
                content=generate_latest(selected_metrics.registry),
                headers={"Content-Type": CONTENT_TYPE_LATEST},
            )

    @app.get("/v1/control/devices", response_model=DeviceListResponse)
    async def list_devices() -> DeviceListResponse:
        devices = [_device_view(connection) for connection in registry.connected_devices()]
        return DeviceListResponse(devices=devices)

    @app.get("/v1/control/devices/{device_id}", response_model=DeviceView)
    async def get_device(device_id: str) -> DeviceView | JSONResponse:
        connection = registry.get_connection(device_id)
        if connection is None:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "DEVICE_NOT_CONNECTED",
                        "message": f"device is not connected: {device_id}",
                    }
                },
            )
        return _device_view(connection)

    @app.get("/v1/control/devices/{device_id}/touch")
    async def get_touch_state(device_id: str) -> JSONResponse:
        if registry.get_connection(device_id) is None:
            return _error_response(
                404,
                "DEVICE_NOT_CONNECTED",
                f"device is not connected: {device_id}",
            )
        touch = touch_state.last_touch(device_id) if touch_state is not None else None
        return JSONResponse(
            content={
                "touch": touch.model_dump(mode="json", exclude_none=True)
                if touch is not None
                else None
            }
        )

    @app.post("/v1/control/devices/{device_id}/commands")
    async def send_command(device_id: str, request: CommandRequest) -> JSONResponse:
        try:
            result = await registry.send_command(
                device_id,
                request.name,
                request.args,
                turn_id=request.turn_id,
            )
        except DeviceNotConnectedError:
            return _error_response(
                404, "DEVICE_NOT_CONNECTED", f"device is not connected: {device_id}"
            )
        except DeviceDisconnectedError:
            return _error_response(409, "DEVICE_NOT_CONNECTED", f"device disconnected: {device_id}")
        except CommandTimedOutError:
            return _error_response(504, "COMMAND_TIMEOUT", f"command timed out: {device_id}")
        except DeviceCapabilityError as error:
            return _capability_error_response(error)
        except MotionSafetyError:
            return _error_response(
                422,
                "INVALID_ARGUMENT",
                "command exceeds the device motion safety profile",
            )
        except ValidationError:
            return _error_response(422, "INVALID_ARGUMENT", "command arguments are invalid")
        payload = result.payload.model_dump(mode="json")
        return JSONResponse(
            content={"request_id": str(result.request_id), **payload},
        )

    @app.post(
        "/v1/control/devices/{device_id}/speech", status_code=202, response_model=SpeechStatus
    )
    async def start_speech(
        device_id: DeviceId, request: SpeechRequest
    ) -> SpeechStatus | JSONResponse:
        if speech_turn_service is None:
            return _error_response(503, "SPEECH_UNAVAILABLE", "speech service is unavailable")
        try:
            return await speech_turn_service.start(device_id, text=request.text)
        except SpeechUnavailableError:
            return _error_response(503, "SPEECH_UNAVAILABLE", "speech service is unavailable")
        except TurnBusyError:
            return _error_response(409, "TURN_BUSY", "device already has an active turn")
        except DeviceNotConnectedError:
            return _error_response(404, "DEVICE_NOT_CONNECTED", "device is not connected")
        except DeviceDisconnectedError:
            return _error_response(409, "DEVICE_NOT_CONNECTED", "device disconnected")
        except DeviceCapabilityError as error:
            return _capability_error_response(error)
        except StaleTurnError:
            return _error_response(409, "TURN_CANCELLED", "speech turn was cancelled")

    @app.get("/v1/control/devices/{device_id}/speech/{turn_id}", response_model=SpeechStatus)
    async def get_speech_status(device_id: DeviceId, turn_id: UUID) -> SpeechStatus | JSONResponse:
        if speech_turn_service is None:
            return _error_response(503, "SPEECH_UNAVAILABLE", "speech service is unavailable")
        try:
            return speech_turn_service.get(device_id, turn_id)
        except SpeechNotFoundError:
            return _error_response(404, "SPEECH_NOT_FOUND", "speech result is not retained")

    @app.post("/v1/control/devices/{device_id}/speech/cancel")
    async def cancel_speech(device_id: str, request: CancelSpeechRequest) -> JSONResponse:
        if turn_coordinator is not None:
            turn = turn_coordinator.current(device_id)
            if (
                turn is not None
                and turn.turn_id == request.turn_id
                and turn.state is TurnState.CAPTURING
            ):
                return _error_response(
                    409,
                    "TURN_CAPTURING",
                    "cannot cancel speech while the target turn is capturing input",
                )
            cancelled = await turn_coordinator.cancel_turn(
                device_id,
                request.turn_id,
                reason="CONTROL_API_CANCEL",
            )
            if not cancelled:
                return _error_response(409, "TURN_NOT_ACTIVE", "target turn is not active")
        try:
            result = await registry.send_command(
                device_id,
                "speech.cancel",
                {},
                turn_id=request.turn_id,
            )
        except DeviceNotConnectedError:
            return _error_response(
                404, "DEVICE_NOT_CONNECTED", f"device is not connected: {device_id}"
            )
        except DeviceDisconnectedError:
            return _error_response(409, "DEVICE_NOT_CONNECTED", f"device disconnected: {device_id}")
        except CommandTimedOutError:
            return _error_response(504, "COMMAND_TIMEOUT", f"command timed out: {device_id}")
        payload = result.payload.model_dump(mode="json")
        return JSONResponse(content={"request_id": str(result.request_id), **payload})

    return app


def _device_view(connection: DeviceConnection) -> DeviceView:
    return DeviceView(
        device_id=connection.device_id,
        connected=True,
        device_name=connection.hello.payload.device_name,
        firmware_version=connection.hello.payload.firmware_version,
        hardware_model=connection.hello.payload.hardware_model,
        protocol_version=connection.protocol_version,
        capabilities=connection.hello.payload.capabilities.model_dump(),
    )


def _error_response(
    status_code: int, code: str, message: str, *, details: dict[str, object] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {"code": code, "message": message, **({"details": details} if details else {})}
        },
    )


def _capture_error_response(error: CaptureCommandFailedError) -> JSONResponse:
    if error.code == "CAPTURE_CAPACITY":
        return _error_response(
            429, error.code, "capture capacity unavailable", details=error.details
        )
    return _error_response(409, error.code, "device capture failed", details=error.details)


def _capability_error_response(error: DeviceCapabilityError) -> JSONResponse:
    return _error_response(
        409,
        "CAPABILITY_UNAVAILABLE",
        f"device capability is unavailable: {error.capability}",
    )


async def _not_configured() -> bool:
    return False
