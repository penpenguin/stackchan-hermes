# Software and dependency inventory

Resolved on 2026-11-20. `pyproject.toml` contains compatible ranges; `uv.lock` is the executable
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
| MCP Python SDK | 2.3.0 | Current stable v2 stdio MCP server line |
| websockets | 17.1 | Simulator/device WebSocket client support |
| zeroconf | 0.150.0 | Optional mDNS discovery/advertising implementation |
| numpy / soundfile | 2.5.2 / 0.14.0 | PCM processing and WAV I/O |
| opuslib-next | 1.3.1 | Maintained libopus ctypes binding selected behind an adapter |
| Pillow | 13.0.0 | Bounded JPEG structure verification and full decode before capture storage |
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
- Firmware release builds use ESP-IDF v5.5.6, CMake 3.28.3, Ninja 1.11.1 and
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

## Security review 2026-11-20

The host gate exports every extra and dependency group from `uv.lock` and audits the
resulting `pylock.toml` with `pip-audit --locked --strict`. All 104 third-party packages,
including the optional STT and Windows packages, were checked against PyPI. The previous
lock produced findings for nine packages. The updated lock produced zero findings and zero
skips. [PyPI release vulnerability data](https://docs.pypi.org/api/json/#get-a-release)

| Package | Previous | Updated |
| --- | --- | --- |
| certifi | 2026.7.22 | 2026.10.23 |
| filelock | 3.32.4 | 4.2.12 |
| mcp / mcp-types | 2.1.1 | 2.3.0 |
| msgpack | 1.2.2 | 1.2.4 |
| opentelemetry-api | 1.44.0 | 1.45.2 |
| Pillow | 12.3.0 | 13.0.0 |
| PyJWT | 2.13.0 | 2.15.1 |
| setuptools | 84.0.0 | 84.2.1 |
| urllib3 | 2.7.0 | 2.8.0 |

Pillow and filelock crossed major versions. The SDK companion package `mcp-types` moved
with `mcp`. The two pinned CI actions returned no OSV matches for their release versions.

Espressif's SDK-wide report listed 20 findings for ESP-IDF 5.5.4 and six for 5.5.6.
The CoreS3 release was rebuilt with 5.5.6. The Mbed TLS findings in the previous report
are absent from the new one. [5.5.4 report](https://github.com/espressif/esp-idf-security-dashboard/blob/main/data/v5.5.4.json)
and [5.5.6 report](https://github.com/espressif/esp-idf-security-dashboard/blob/main/data/v5.5.6.json)

| Remaining SDK findings | CoreS3 release evidence |
| --- | --- |
| NimBLE CVE-2026-45812, CVE-2026-45813 | Peripheral and broadcaster roles are enabled. Central and observer roles are disabled. The ELF contains the GATT server and advertiser, and contains neither the legacy advertising report handler nor the BASS service. |
| cJSON CVE-2026-67215, CVE-2026-67216, CVE-2026-67217 | The ELF contains neither the affected JSON Patch entry points nor `cJSON_Compare`. |
| cJSON CVE-2026-16554 | The string printer is linked. The reported input size exceeds the board's 8 MiB PSRAM. The library version still matches the advisory. |

OSV commit queries covered the vendor snapshot, SDK, six fetched Git repositories and
50 managed components with a recorded source commit. For the ten remaining components
we checked published GitHub advisories in their eight source repositories. All 60 managed
content hashes and all six Git pins verified locally. These results apply to the reviewed
CoreS3 build and its configuration. [Release manifest](license-inventory/cores3-release.json)

- Xiaozhi matched CVE-2026-13489 and CVE-2026-13491. Its cloud MCP and MQTT handlers are
  excluded from compilation and linking by the release gate.
  [MCP record](https://osv.dev/vulnerability/CVE-2026-13489) and [MQTT record](https://osv.dev/vulnerability/CVE-2026-13491)
- The ESP-USB repository matched three records. Two concern the separate HID driver.
  The UVC driver is locked at 2.3.1 because `esp_video` requires 2.3.x. Its USB camera
  support and descriptor printing are disabled in this build, and the UVC archive is
  absent from the link map. Enabling UVC requires updating the dependency chain to use
  the fix in 2.4.0 or later. [Espressif UVC advisory](https://github.com/espressif/esp-usb/security/advisories/GHSA-g65h-9ggq-9827)

The isolated SDK build environment contains 62 Python packages. The audit reported
10 findings for `cryptography==44.0.3`, 12 for `urllib3==1.26.20` and two for
`ecdsa==0.19.2`. These 24 findings remain in the build tools. The reviewed
ESP-IDF 5.5 constraints cap the first two below the published fixes. PyPI listed no
fixed version for either ecdsa finding. These packages are outside the Bridge lock and
are not shipped in the CoreS3 images. [Espressif 5.5 build constraints](https://dl.espressif.com/dl/esp-idf/espidf.constraints.v5.5.txt)

## Review triggers

Update the lock only in a dedicated change, run `./scripts/verify-host.sh`, review new licenses and
native artifacts, and document breaking majors. In particular, test MCP SDK major changes and
Opus packet interoperability before accepting them.
