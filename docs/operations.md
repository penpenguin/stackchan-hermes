# Development and operations setup

The CFW uses local functions and the selected Hermes Bridge. Legacy AI.Agent, EzData, account
linking, App Center, cloud calls and OTA updates have been removed. Firmware updates use USB;
on-device Wi-Fi provisioning uses a local hotspot. See [network policy](network-policy.md) for
endpoint selection, retained settings, redirect handling and the hardware verification boundary.

## Supported host toolchain

Host-side development requires Python 3.12, `uv`, Git, ffmpeg with Opus support, libopus and
libsndfile. Firmware verification additionally requires ESP-IDF v5.5.4 and its matching CMake,
Ninja, compiler and esptool dependencies. WSL2 is supported for attended USB and LAN verification,
but is not required for host-only tests. Exact versions and availability observed during acceptance
belong in `verification-report.md`, not in this reusable setup guide.

## Host bootstrap

No global `pip install` is used.

```bash
uv sync --locked
./scripts/bootstrap-check.sh --json
./scripts/verify-host.sh
```

`uv.lock` is committed and includes default plus optional dependency resolution. The heavy
`faster-whisper` adapter is declared under the `stt-local` extra and is not installed by the
default sync:

```bash
uv sync --locked --extra stt-local
```

## ESP-IDF activation and reproducible prerequisite

Official StackChan currently requires ESP-IDF v5.5.4. The official Espressif Linux guide lists
Git, wget, flex, bison, gperf, Python/venv, CMake, Ninja, ccache, libffi, libssl, dfu-util, and
libusb as prerequisites. This repository does not run `apt`, Homebrew, or profile edits.

Use an isolated ESP-IDF v5.5.4 checkout at the reviewed commit
`735507283d5b2f9fb363a1901172dbd9e847945d`. Activate it only in the Firmware shell, replacing
`<idf-root>` with that checkout path:

```bash
. <idf-root>/export.sh
```

For a new host, the equivalent official isolated setup is:

```bash
git clone -b v5.5.4 --recursive https://github.com/espressif/esp-idf.git <idf-root>
cd <idf-root>
./install.sh esp32s3
. ./export.sh
```

Activate `export.sh` only in the firmware shell. Do not add it globally to the shell profile.
Then `./scripts/verify-firmware.sh` must fail or pass explicitly; it never skips missing IDF.

## WSL2 USB prerequisite (manual Windows action)

WSL2 does not expose USB serial devices by default. Microsoft documents `usbipd-win`:

```powershell
usbipd list
usbipd bind --busid <busid>       # elevated PowerShell, once
usbipd attach --wsl --busid <busid>
```

After attachment, verify a unique device under `/dev/serial/by-id` or `/dev/ttyACM*`. Never infer
the flash target when multiple ports exist.

## WSL2 mirrored LAN prerequisite (manual Windows action)

Mirrored WSL can expose a Linux listener to the LAN, but Microsoft documents that Hyper-V
firewall must allow the inbound connection. Do not broaden the WSL default inbound action for
this project. After explicit operator approval, use an elevated PowerShell to create only a named
TCP 8765 rule limited to the local subnet:

```powershell
New-NetFirewallHyperVRule `
  -Name "StackChanHermesBridge8765" `
  -DisplayName "StackChan Hermes Bridge temporary" `
  -Direction Inbound `
  -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' `
  -Protocol TCP `
  -LocalPorts 8765 `
  -RemoteAddresses LocalSubnet `
  -Action Allow `
  -Enabled True
```

Confirm the rule before the first physical scenario:

```powershell
Get-NetFirewallHyperVRule -Name "StackChanHermesBridge8765"
```

For one continuous hardware campaign, keep exactly one enabled rule with that name and scope. Do
not delete and recreate it between scenarios. While the Bridge is stopped, verify that no process
is listening on 8765/8766. The rule is retained until final Goal cleanup (or an explicitly requested
final abort cleanup), when that exact name is removed once:

```powershell
Remove-NetFirewallHyperVRule -Name "StackChanHermesBridge8765"
```

After final cleanup, verify zero rules with that name, WSL `DefaultInboundAction=Block`, no listener
on 8765/8766 and detached USB. This OS security-boundary change is never automated by repository
scripts. The acceptance campaign used this narrow rule and removed it during final cleanup.
Historical connectivity evidence is recorded in `hardware-test-report.md`; a new physical campaign
must create and remove its own explicitly approved rule. See
[Microsoft's mirrored-mode networking guidance](https://learn.microsoft.com/en-us/windows/wsl/networking#mirrored-mode-networking).

## Hermes prerequisite (external process)

Hermes remains independently installed and configured. Its public API server must expose
`GET /health`, `GET /v1/capabilities`, and `POST /v1/responses`, with bearer authentication and
`X-Hermes-Session-Key`. Do not modify `~/.hermes/config.yaml` automatically.

When the user has supplied a local API key, verify without printing it:

```bash
curl -fsS http://127.0.0.1:8642/health
curl -fsS -H "Authorization: Bearer ${HERMES_API_KEY}" \
  http://127.0.0.1:8642/v1/capabilities
```

The Bridge readiness check must remain false if required capabilities are absent. It must not
fall back to `/api/ws`. The health and capabilities requests share one wall-clock deadline of
`hermes.timeout_seconds`, including streamed response bodies; expiry reports readiness failure.

## Runtime setup

Create ignored local files and protect the environment file:

```bash
cp config.example.toml config.toml
cp .env.example .env
chmod 600 .env config.toml
set -a
. ./.env
set +a
uv run stackchan-bridge serve --config config.toml
```

The generic `STACKCHAN_<SECTION>__<FIELD>` environment form overrides TOML; named CLI bind/port
arguments override both. Secrets are accepted only from the environment variable named by each
adapter. Bridge never mutates `.env`, Hermes config, shell profiles or OS services.

Readiness and inventory:

```bash
uv run stackchan-bridge doctor --config config.toml --json
uv run stackchan-bridge devices --config config.toml --json
uv run stackchan-bridge captures list --config config.toml --json
uv run stackchan-bridge captures purge --config config.toml --json
```

`/health/ready` checks configuration, writable capture storage, libopus and Hermes public
health/capabilities without submitting STT audio or TTS text for inference. `doctor` checks config,
ports, capture write access, Bridge readiness, configured STT/TTS adapter state, the public Hermes
surfaces, MCP example, mDNS, connected device and a verified firmware backup. For faster-whisper it
reports `stt_model_cache: missing` before the first download; it does not start a network download
itself. Validate provider inference only through an explicit voice diagnostic.

`POST /v1/control/devices/{device_id}/speech/cancel` rejects a target turn in `CAPTURING` with
HTTP 409 / `TURN_CAPTURING`, without cancelling the turn or sending a Firmware command. The
current protocol's `speech.cancel` stops playback, not microphone recording; allow the device's
input end or recording deadline to close the input before retrying cancellation.
Incoming `touch.tap` and `touch.long_press` events during `CAPTURING` likewise update touch
telemetry without cancelling the recording turn or sending `speech.cancel`. After capture,
repeated touches can still cancel processing or playback as barge-in.

When a device already has 16 commands awaiting results, Control API command, capture, and vision
requests return HTTP 429 / `COMMAND_QUEUE_FULL` without queuing another command. Defer retries
until pending commands finish or time out; existing work is retained and a freed slot is reusable.

## Device token and Hermes/MCP configuration

Generate a token once, copy only the derived hash to TOML, and provision the raw token only to the
matching device. Do not reuse the Hermes key.

```bash
uv run stackchan-bridge token create --device-id stackchan-001 --json
```

Merge `examples/hermes-config.yaml` manually after replacing its absolute path. It launches
`stackchan-mcp` over stdio and points it only at the loopback Control API. Standard output is
reserved for MCP framing; logs go to stderr.

## Simulator and fault reproduction

```bash
./scripts/run-simulator-e2e.sh
uv run stackchan-simulator --bridge ws://127.0.0.1:8765/v1/device/ws \
  --device-id sim-001 --token-env STACKCHAN_SIM_TOKEN
uv run stackchan-simulator --bridge ws://127.0.0.1:8765/v1/device/ws \
  --device-id sim-001 --token-env STACKCHAN_SIM_TOKEN --fault malformed-json
```

Named fault modes are `malformed-json`, `malformed-opus`, `duplicate-message`, and `disconnect`.
`--protocol-version 2`, a wrong runtime token, and `--command-delay-ms` cover unsupported version,
authentication and timeout paths. Voice mode waits 30 seconds for the first or a subsequent output
segment by default. Set `--output-segment-grace-ms` to cover the initial STT/Hermes/TTS response
latency as well as later TTS segment latency when using slower providers. Each started segment has
a fixed deadline of its advertised duration plus this grace; incoming packets do not extend it.
Recorded output across all segments is limited to 120 seconds of 16 kHz mono PCM. Missing ends,
excess output, any WebSocket disconnect (including between segments), or an output end reason
other than `completed` fail the turn without saving partial audio. Only grace expiry after a
completed segment is treated as successful output completion. Input WAV headers are checked before
decoding: at most 15 seconds and 5,760,000 source sample values (frames times channels).
Reconnect uses 1/2/4/8/16/30-second bounded backoff.

## Logs, metrics, media and debug reports

- JSON logs are enabled with `observability.json_logs`; transcript logging additionally requires
  `privacy_debug_transcripts=true`.
- `GET http://127.0.0.1:8766/metrics` exposes machine-readable Prometheus metrics. For an attended
  touch check with exactly one reviewed device connected, record `touch_events_total`,
  `audio_input_frames_total` and `active_turns` immediately before and after the press. Only a
  `touch_events_total` increase proves that a touch event reached the Bridge; it contains no
  device, coordinate or content labels.
- Captures expire after ten minutes by default. `captures.persist=true` is explicit archival
  opt-in; expired records are no longer served even when the file is retained. Vision turns are
  non-archival: their owned capture record and file are deleted immediately after reading the
  JPEG, before Hermes/TTS work, even with persistence enabled or if reading fails. Unrelated
  captures are preserved.
- Capture protocol 2 requires Bridge, Firmware and Simulator to be upgraded together. Control
  success requires both image storage and the Firmware completion proof after cleanup. The default
  ten-second monotonic deadline starts at reservation, covers command dispatch and upload, and is
  separate from image retention. Body reading is limited to the smaller of ten seconds and the
  remaining transaction budget; timeout is HTTP 408 / `CAPTURE_UPLOAD_TIMEOUT`. Cancellation
  interrupts reading and closes temporary files. See [capture protocol](protocol-v1.md#capture-transaction-protocol-2).
- To investigate a capture, correlate `capture_id`, stage, elapsed time, planned JPEG bytes,
  actual wire bytes, attempt, HTTP status, error and busy state in Firmware logs. Structured Bridge
  logs retain capture ID, stage, reason and image-saved status. HTTP headers, credentials and image
  contents are excluded. A saved image without Firmware completion produces
  `CAPTURE_COMPLETION_TIMEOUT`; it is not reported as a completed capture.
- Hardware validation starts with stationary captures and requires the project's separate backup,
  port and authorization checks. Build and fault-injection tests do not establish the cause of the
  original device failure or physical timing under load.
- Microphone WAV storage is off by default. If enabled, use a private ignored directory and a short
  `audio.debug_ttl_seconds`; the runtime emits a warning and startup purge. While the Gateway is
  running, enabled debug storage is purged every `min(60, audio.debug_ttl_seconds)` seconds.
  Temporary filesystem errors are logged and retried on the next interval; cleanup stops with
  the Gateway. Only owned, expired WAV files are removed.
- Create a new mode-0600 report without config/environment contents:

```bash
./scripts/create-debug-report.sh --output debug-reports/report.txt
./scripts/create-debug-report.sh --output debug-reports/report-with-log.txt --log /path/to/bridge.log
```

Optional text logs are capped at 1 MiB and credentials/inline image data are redacted. Inspect the
report manually before sharing.

## launchd and systemd

The examples under `examples/launchd` and `examples/systemd` restart only after abnormal exits,
wait ten seconds between attempts, and keep secrets in a mode-0600 external environment file.
Replace all paths and create log/runtime directories manually. Hermes is not an ordering
dependency: Bridge starts unready and recovers through repeated readiness probes when Hermes
becomes available.

## Firmware backup, build, flash and restore

The backup command is dry-run unless `--execute-read` is supplied. Partition values must come from
the verified device/baseline, not this example:

```bash
./scripts/backup-firmware.sh --port /dev/serial/by-id/REVIEWED-ID \
  --output-dir firmware/backups/device-001 --boot-log /tmp/factory-boot.log \
  --firmware-version 1.5.1 --partition-offset 0x8000 --partition-size 0xC00
```

Only after reviewing that plan, confirming exactly one K151 and satisfying every checklist item,
repeat with `--execute-read`. The script reads 16 MiB plus the partition table, records SHA-256,
metadata and a restore command, but never writes flash. The six Git dependencies are ignored
working copies. Fetch them from the reviewed upstream manifest once, then verify their exact
commits and the reviewed xiaozhi patch before every build:

```bash
. <idf-root>/export.sh
cd firmware
python3 ./fetch_repos.py
python3 ./verify_upstream_dependencies.py
python3 ./verify_managed_components.py
cd ..
./scripts/verify-firmware.sh
```

The verification gate builds from a fresh temporary configuration with
`firmware/sdkconfig.hermes.defaults`, which explicitly enables the Bridge client, USB
provisioning and the fail-closed physical head-motion lock. It rejects the candidate unless the
generated sdkconfig contains `CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y`. To retain a local
release-candidate artifact without altering the ignored default `firmware/sdkconfig`, use a
private configuration path and a clearly named build directory:

```bash
cd firmware
idf.py -B build-hermes-usb-console \
  -D SDKCONFIG=/tmp/stackchan-hermes-usb-console-sdkconfig \
  -D "SDKCONFIG_DEFAULTS=$PWD/sdkconfig.defaults;$PWD/sdkconfig.hermes.defaults" build
```

After a safe physical boot, the serial REPL accepts validated NVS updates such as these. Persistent
command history is disabled and command results never print the token, but ESP-IDF linenoise can
echo characters typed into the terminal. Disable terminal/session logging or use a
response-suppressing serial utility for `set-token`; never send it through a recorded monitor.
All changes require reboot:

```text
stackchan-hermes set-device-id stackchan-001
stackchan-hermes set-url ws://192.0.2.10:8765/v1/device/ws
stackchan-hermes set-fallback-url ws://192.0.2.11:8765/v1/device/ws
stackchan-hermes set-discovery enabled
stackchan-hermes set-token <device-token>
stackchan-hermes set-volume 65
stackchan-hermes set-brightness 70
stackchan-hermes set-touch enabled
```

After an authenticated Bridge session is established, an attended, motion-free HW-04 observation
can apply and restore a bounded visual state through the loopback Control API. Supply the brightness
that was configured before the test; do not guess it. This path refuses hardware other than
`M5STACK-K151`, requires the Firmware to advertise `head=false`, and sends no head command:

```bash
uv run python scripts/hardware-smoke-test.py \
  --device-id stackchan-001 \
  --safe-visual \
  --restore-brightness 70 \
  --hold-seconds 10
```

The operator must observe both the temporary happy/dim-blue/35% state and the return to
idle/LED-off/original brightness. An HTTP acknowledgement alone is not physical evidence. If one
restore command fails, the script still attempts the other restores and exits nonzero.

For an attended HW-05 measurement, start the GET-only observer while the reviewed device is
connected, then stop and restart the Bridge in a separate terminal. The observer requires
`M5STACK-K151`, `connected=true` and `head=false`, ignores a single failed poll, and measures from
the first sample in a confirmed outage until the Control API sees the device again:

```bash
uv run python scripts/hardware-reconnect-observer.py --device-id stackchan-001
```

Its JSON proves only the externally observed transport interval. The operator must separately
confirm the reconnect display, and a serial observation is required before claiming that Firmware
did not reboot. The observer does not stop/start Bridge or send a device command.

An integrated image that builds successfully is still not authorization to flash. Confirm all
three Hermes settings in the generated sdkconfig, recheck the retained image digest and review
the exact `idf.py -B build-hermes-usb-console -p <reviewed-port> flash` command only after
HW-01. Execute it only with explicit approval; it is intentionally not automated here. Restore
uses only the command recorded beside the verified backup after a separate hardware-risk review.

## Bridge update and rollback

Stop the user service, preserve ignored config/environment/runtime data, update in a dedicated Git
branch, run `uv sync --locked` and `./scripts/verify-host.sh`, then restart and check doctor. Roll
back by checking out the previously reviewed commit in a clean worktree; never use a destructive
reset on a worktree containing user changes.
