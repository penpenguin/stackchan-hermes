"""Read-only host prerequisite checks used during bootstrap."""

from __future__ import annotations

import json
import socket
from collections.abc import Callable, Mapping
from ctypes.util import find_library as system_find_library
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from hmac import compare_digest
from importlib.util import find_spec
from pathlib import Path
from shutil import which as system_which
from stat import S_ISREG
from tempfile import NamedTemporaryFile

import httpx

from stackchan_bridge.config import BridgeSettings
from stackchan_bridge.hermes.client import parse_hermes_capabilities

Which = Callable[[str], str | None]
FindLibrary = Callable[[str], str | None]
PortChecker = Callable[[str, int], bool]

_MAX_DOCTOR_RESPONSE_BYTES = 1_048_576
_FACTORY_FLASH_BYTES = 16 * 1024 * 1024


class CheckStatus(StrEnum):
    """Availability state for one prerequisite."""

    AVAILABLE = "available"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class HostCheck:
    """Result of one non-mutating prerequisite check."""

    name: str
    status: CheckStatus
    required: bool
    detail: str | None

    def as_dict(self) -> dict[str, str | bool | None]:
        return {
            "status": self.status.value,
            "required": self.required,
            "detail": self.detail,
        }


_COMMANDS: tuple[tuple[str, bool], ...] = (
    ("python3.12", True),
    ("uv", True),
    ("git", True),
    ("ffmpeg", True),
    ("idf.py", False),
    ("cmake", False),
    ("ninja", False),
    ("hermes", False),
)


def inspect_host(
    *,
    which: Which = system_which,
    find_library: FindLibrary = system_find_library,
) -> tuple[HostCheck, ...]:
    """Inspect local tools without network calls or filesystem writes."""

    checks = [
        HostCheck(
            name=name,
            status=CheckStatus.AVAILABLE if (path := which(name)) else CheckStatus.MISSING,
            required=required,
            detail=path,
        )
        for name, required in _COMMANDS
    ]
    opus_path = find_library("opus")
    checks.append(
        HostCheck(
            name="libopus",
            status=CheckStatus.AVAILABLE if opus_path else CheckStatus.MISSING,
            required=True,
            detail=opus_path,
        )
    )
    return tuple(checks)


def host_is_ready(checks: tuple[HostCheck, ...]) -> bool:
    """Return whether every host-side required check is available."""

    return all(check.status is CheckStatus.AVAILABLE for check in checks if check.required)


def inspect_online(
    settings: BridgeSettings,
    *,
    environment: Mapping[str, str],
    host_checks: tuple[HostCheck, ...],
    transport: httpx.BaseTransport | None = None,
    port_checker: PortChecker | None = None,
    project_root: Path | None = None,
) -> tuple[HostCheck, ...]:
    """Inspect configured public services and local runtime contracts without media requests."""

    root = project_root or Path(__file__).resolve().parents[3]
    checks = list(host_checks)
    configuration_ready = _configuration_ready(settings, environment)
    checks.append(_check("configuration", configuration_ready, required=True))

    control_payload: dict[str, object] | None = None
    health_payload: dict[str, object] | None = None
    capabilities_payload: dict[str, object] | None = None
    with httpx.Client(timeout=5, transport=transport, trust_env=False) as client:
        control_payload = _safe_get_json_object(
            client,
            _control_url(settings, "/health/ready"),
        )
        try:
            authorization = _hermes_authorization(settings)
        except ValueError:
            authorization = None
        if authorization is not None:
            health_payload = _safe_get_json_object(
                client,
                f"{settings.hermes.base_url}{settings.hermes.health_path}",
                headers=authorization,
            )
            capabilities_payload = _safe_get_json_object(
                client,
                f"{settings.hermes.base_url}{settings.hermes.capabilities_path}",
                headers=authorization,
            )

    bridge_checks = control_payload.get("checks") if control_payload is not None else None
    valid_bridge_checks = bridge_checks if isinstance(bridge_checks, dict) else {}
    bridge_ready = control_payload is not None and control_payload.get("ready") is True
    checks.append(_check("bridge_readiness", bridge_ready, required=True))

    capture_writable = _directory_is_writable(settings.captures.directory)
    capture_ready = valid_bridge_checks.get("capture_store") is True
    checks.append(
        _check(
            "capture_storage",
            capture_writable and capture_ready,
            required=True,
            detail=str(settings.captures.directory),
        )
    )
    checks.append(_check("stt", valid_bridge_checks.get("stt") is True, required=True))
    if settings.stt.adapter == "faster-whisper":
        model_cached = faster_whisper_model_is_cached(
            settings.stt.model_name,
            environment=environment,
        )
        checks.append(
            _check(
                "stt_model_cache",
                model_cached,
                required=True,
                detail="cached" if model_cached else "initial download required",
            )
        )
    checks.append(_check("tts", valid_bridge_checks.get("tts") is True, required=True))

    health_ready = health_payload is not None and health_payload.get("status") == "ok"
    checks.append(_check("hermes_health", health_ready, required=True))
    capabilities_ready = capabilities_payload is not None
    checks.append(_check("hermes_capabilities", capabilities_ready, required=True))
    responses_ready = _responses_capabilities_ready(settings, capabilities_payload)
    checks.append(_check("responses_api", responses_ready, required=True))

    selected_port_checker = port_checker or _port_is_open
    checks.append(
        _check(
            "control_port",
            selected_port_checker(settings.control_api.host, settings.control_api.port),
            required=True,
            detail=f"{settings.control_api.host}:{settings.control_api.port}",
        )
    )
    gateway_probe_host = _connectable_host(settings.device_gateway.host)
    checks.append(
        _check(
            "device_gateway_port",
            selected_port_checker(gateway_probe_host, settings.device_gateway.port),
            required=True,
            detail=f"{gateway_probe_host}:{settings.device_gateway.port}",
        )
    )

    connected_devices = (
        control_payload.get("connected_devices") if control_payload is not None else None
    )
    connected_count = connected_devices if isinstance(connected_devices, int) else 0
    checks.append(
        _check(
            "connected_device",
            connected_count > 0,
            required=False,
            detail=f"{connected_count} connected",
        )
    )
    checks.append(
        _check(
            "mcp_config_example",
            _mcp_example_is_valid(root / "examples" / "hermes-config.yaml"),
            required=True,
        )
    )
    checks.append(
        _check(
            "mdns",
            not settings.mdns.enabled or find_spec("zeroconf") is not None,
            required=False,
            detail="enabled" if settings.mdns.enabled else "disabled",
        )
    )
    checks.append(
        _check(
            "firmware_backup",
            firmware_backup_is_verified(root / "firmware" / "backups"),
            required=False,
            detail="verified 16 MiB backup",
        )
    )
    return tuple(checks)


def _check(
    name: str,
    available: bool,
    *,
    required: bool,
    detail: str | None = None,
) -> HostCheck:
    return HostCheck(
        name=name,
        status=CheckStatus.AVAILABLE if available else CheckStatus.MISSING,
        required=required,
        detail=detail,
    )


def _configuration_ready(settings: BridgeSettings, environment: Mapping[str, str]) -> bool:
    if settings.hermes.api_key is None:
        return False
    allowed = set(settings.security.allowed_devices)
    hashes = set(settings.security.device_token_hashes)
    if not hashes.issubset(allowed):
        return False
    missing = allowed.difference(hashes)
    raw_token = environment.get(settings.security.device_token_env)
    return not missing or (len(missing) == 1 and bool(raw_token))


def _hermes_authorization(settings: BridgeSettings) -> dict[str, str]:
    api_key = settings.hermes.api_key
    if api_key is None:
        raise ValueError("Hermes API key is unavailable")
    return {"Authorization": f"Bearer {api_key.get_secret_value()}"}


def _control_url(settings: BridgeSettings, path: str) -> str:
    host = settings.control_api.host
    authority = f"[{host}]" if ":" in host else host
    return f"http://{authority}:{settings.control_api.port}{path}"


def _get_json_object(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    with client.stream("GET", url, headers=headers) as response:
        response.raise_for_status()
        body = bytearray()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > _MAX_DOCTOR_RESPONSE_BYTES:
                raise ValueError("doctor response exceeds limit")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("doctor response must be an object")
    return payload


def _safe_get_json_object(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, object] | None:
    try:
        return _get_json_object(client, url, headers=headers)
    except (httpx.HTTPError, ValueError):
        return None


def _responses_capabilities_ready(
    settings: BridgeSettings,
    payload: dict[str, object] | None,
) -> bool:
    if payload is None:
        return False
    try:
        capabilities = parse_hermes_capabilities(payload)
    except ValueError:
        return False
    model_available = bool(settings.hermes.model) or bool(capabilities.models)
    core_capabilities = all(
        (
            capabilities.responses_api,
            capabilities.streaming,
            capabilities.session_key_header,
            capabilities.input_image,
        )
    )
    return (
        model_available
        and core_capabilities
        and capabilities.skills_endpoint is not None
        and capabilities.toolsets_endpoint is not None
    )


def _directory_is_writable(directory: Path) -> bool:
    try:
        with NamedTemporaryFile(dir=directory, prefix=".doctor-", delete=True) as probe:
            probe.write(b"ready")
            probe.flush()
    except OSError:
        return False
    return True


def _connectable_host(host: str) -> str:
    if host in {"0.0.0.0", ""}:
        return "127.0.0.1"
    if host == "::":
        return "::1"
    return host


def _port_is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((_connectable_host(host), port), timeout=0.5):
            return True
    except OSError:
        return False


def _mcp_example_is_valid(path: Path) -> bool:
    try:
        if path.is_symlink() or not S_ISREG(path.stat().st_mode) or path.stat().st_size > 65_536:
            return False
        content = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return "stackchan-mcp" in content and "http://127.0.0.1:" in content


def firmware_backup_is_verified(directory: Path) -> bool:
    """Return true only for a complete factory image whose recorded digest matches."""

    try:
        if directory.is_symlink():
            return False
        backup_directories = (
            directory,
            *(child for child in directory.iterdir() if not child.is_symlink() and child.is_dir()),
        )
        candidates = tuple(
            candidate
            for backup_directory in backup_directories
            for candidate in backup_directory.glob("*.bin")
        )
    except OSError:
        return False
    for candidate in candidates:
        try:
            if candidate.is_symlink() or candidate.stat().st_size != _FACTORY_FLASH_BYTES:
                continue
            checksum = candidate.with_suffix(candidate.suffix + ".sha256")
            if checksum.is_symlink() or not checksum.is_file():
                continue
            fields = checksum.read_text(encoding="ascii").strip().split()
        except (OSError, UnicodeError, IndexError):
            continue
        if not fields:
            continue
        expected_digest = fields[0].lower()
        if len(fields) > 1 and fields[1].lstrip("*") != candidate.name:
            continue
        if len(expected_digest) != 64 or any(
            character not in "0123456789abcdef" for character in expected_digest
        ):
            continue
        actual_digest = sha256()
        try:
            with candidate.open("rb") as backup_file:
                while chunk := backup_file.read(1_048_576):
                    actual_digest.update(chunk)
        except OSError:
            continue
        if compare_digest(actual_digest.hexdigest(), expected_digest):
            return True
    return False


def faster_whisper_model_is_cached(
    model_name: str,
    *,
    environment: Mapping[str, str],
) -> bool:
    """Detect a usable local model without importing faster-whisper or accessing a network."""

    local_model = Path(model_name).expanduser()
    if _valid_whisper_model_directory(local_model):
        return True

    configured_cache = environment.get("HF_HUB_CACHE")
    if configured_cache:
        hub_cache = Path(configured_cache).expanduser()
    elif environment.get("HF_HOME"):
        hub_cache = Path(environment["HF_HOME"]).expanduser() / "hub"
    elif environment.get("XDG_CACHE_HOME"):
        hub_cache = Path(environment["XDG_CACHE_HOME"]).expanduser() / "huggingface" / "hub"
    else:
        hub_cache = Path.home() / ".cache" / "huggingface" / "hub"

    repository = model_name if "/" in model_name else f"Systran/faster-whisper-{model_name}"
    snapshots = hub_cache / f"models--{repository.replace('/', '--')}" / "snapshots"
    try:
        return any(_valid_whisper_model_directory(candidate) for candidate in snapshots.iterdir())
    except OSError:
        return False


def _valid_whisper_model_directory(directory: Path) -> bool:
    try:
        model = directory / "model.bin"
        return (
            directory.is_dir()
            and not directory.is_symlink()
            and model.is_file()
            and not model.is_symlink()
            and model.stat().st_size > 0
        )
    except OSError:
        return False
