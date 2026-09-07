# Software and dependency inventory

Resolved on 2026-09-04. `pyproject.toml` contains compatible ranges; `uv.lock` is the executable
pin with artifact hashes.

ライセンス宣言の確認記録は [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)、
独自部分のライセンス状態と配布条件は [licensing](licensing.md) を参照してください。
全件一覧と保存した通知は [Python](license-inventory/python.md)、[Firmware](license-inventory/firmware.md)、
配布対象ごとの確認範囲と結果は [監査記録](license-audit.md) にあります。
版・hash の固定とライセンス条件の確認は別の確認段階です。

## Core Python runtime

| Package | Locked | Purpose |
| --- | --- | --- |
| FastAPI | 0.141.1 | Device gateway, capture upload, Control API, health |
| Uvicorn | 0.52.4 | ASGI runtime |
| Pydantic / pydantic-settings | 2.13.4 / 2.15.0 | Protocol/config validation |
| httpx | 0.28.1 | Hermes, STT, and TTS HTTP clients |
| MCP Python SDK | 2.1.1 | Current stable v2 stdio MCP server line |
| websockets | 17.1 | Simulator/device WebSocket client support |
| zeroconf | 0.150.0 | Optional mDNS discovery/advertising implementation |
| numpy / soundfile | 2.5.2 / 0.14.0 | PCM processing and WAV I/O |
| opuslib-next | 1.3.1 | Maintained libopus ctypes binding selected behind an adapter |
| Pillow | 12.3.0 | Bounded JPEG structure verification and full decode before capture storage |
| prometheus-client | 0.26.0 | Machine-readable metrics |
| platformdirs | 4.11.5 | Safe host-specific storage defaults |
| python-multipart | 0.0.32 | Bounded capture upload parsing |
| Typer | 0.27.1 | Production Bridge, Simulator and MCP CLI surfaces |

The host implementation uses these packages behind bounded adapters and validated configuration.
Provider-specific additions still require a failing test before import/use.

## Optional runtime

`faster-whisper==1.2.1` is resolved by the `stt-local` extra but is **not installed** by default.
Enable it explicitly with `uv sync --locked --extra stt-local`. Mock STT/TTS remain the initial E2E
providers. VOICEVOX/Piper/generic STT/TTS are external HTTP services and are not auto-installed.

## Development gate

pytest 9.1.1, pytest-asyncio 1.4.0, pytest-cov 7.1.0, Ruff 0.16.5, mypy 2.3.1,
jsonschema 4.26.0/referencing 0.37.0, respx 0.23.1, detect-secrets 1.5.0, and pip-audit
2.10.1 are in the default dev group.

## Native/external software

- Host required now: Python 3.12, uv, Git, ffmpeg with Opus, and a discoverable libopus.
- Firmware baseline build uses the user-installed ESP-IDF v5.5.4, CMake 3.28.3, Ninja 1.11.1 and
  ESP32-S3 GCC 14.2.0. Physical acceptance additionally requires serial/USB access.
- Live runtime acceptance requires an independently configured HermesAgent public API server.
- WSL2 hardware work: user-managed `usbipd-win` attachment is required.

## Firmware source dependencies

The MIT-licensed official StackChan Firmware 1.5.1 snapshot is pinned to commit
`1b5765599fba8aaad1811d9a79358ccc7051f5f3`. `firmware/upstream-lock.json` records the source
tree, ESP-IDF commit, critical file hashes and these fetched repositories:

| Repository | Reviewed ref | License |
| --- | --- | --- |
| mooncake | v2.3.3 | MIT |
| mooncake_log | v1.5.0 | MIT |
| smooth_ui_toolkit | v2.12.0 | MIT |
| xiaozhi-esp32 | v2.2.4 plus reviewed patch | MIT |
| ArduinoJson | v7.4.2 | MIT |
| esp-now | `c33383de97f3ed2fc52117f5ef04f71990432e5d` | Apache-2.0 |

The imported upstream baseline originally resolved 59 managed components. The integrated
`firmware/dependencies.lock` now freezes 60 downloaded ESP-IDF Component Manager entries plus the
ESP-IDF toolchain entry; the only project-added managed dependency is official
`espressif/mdns==1.11.3` (Apache-2.0). Fetched/managed source remains ignored and must pass
`verify_upstream_dependencies.py` and `verify_managed_components.py`; available dependency
upgrades are not accepted implicitly.

## Review triggers

Update the lock only in a dedicated change, run `./scripts/verify-host.sh`, review new licenses and
native artifacts, and document breaking majors. In particular, test MCP SDK major changes and
Opus packet interoperability before accepting them.
