# Architecture

Status: implemented and host-build verified; physical media, bounded motion and failure-recovery
acceptance are Green. Live-provider-dependent voice and vision acceptance are also Green.
CAM-002 live physical vision turn is PASS.

## Responsibilities

```text
StackChan Firmware
  WebSocket text control + raw Opus binary frames
        ⇅
Bridge device gateway ── turn/audio/STT/TTS/capture coordination
        ⇅ HTTP + SSE
Hermes public /v1/responses API

Hermes ── stdio MCP ── StackChan MCP ── loopback Control API ── Bridge ── Firmware
```

- **Firmware** owns hardware I/O, local animation, bounded buffers, reconnection, and final
  physical safety enforcement. It never stores a Hermes key or runs LLM/STT/TTS.
- **Bridge** owns device authentication, protocol state, audio conversion/VAD, adapters,
  turn cancellation, public Hermes API use, captures, health, metrics, and local control.
- **HermesAgent** owns reasoning, memory, skills, MCP/tool decisions, and response generation.
- **Simulator** speaks the same device protocol and enables deterministic host-side tests.

## Network boundary

| Surface | Default bind | Exposure |
| --- | --- | --- |
| Device WebSocket `/v1/device/ws` | `0.0.0.0:8765` | trusted LAN only, bearer device auth |
| Capture upload `/v1/device/captures/{capture_id}` | device gateway | trusted LAN only, device auth |
| Control API `/v1/control/*` | `127.0.0.1:8766` | loopback only |
| Metrics/health | loopback unless explicitly split | local operations |
| Hermes public API | `127.0.0.1:8642` (external process) | loopback only |

LAN-outside exposure, wildcard CORS, Dashboard WebSocket, Hermes imports, and direct database
access are outside the boundary.

## Data paths

- Microphone: 16 kHz mono PCM → FW Opus encoder → raw WebSocket binary packet → Bridge decode.
- Speech: Hermes SSE text → bounded Japanese segments → TTS PCM/WAV → Opus → raw binary packet.
- Camera: authenticated command → JPEG → authenticated multipart upload → bounded TTL store →
  one-time `input_image` data URL when calling Hermes.
- Commands: Hermes MCP → stdio server → loopback Control API → validated device command; Bridge
  and Firmware both validate arguments.

## Implemented package boundaries

- `device_gateway`: authenticated WebSocket/capture upload, registry, capability checks, command
  correlation, binary input routing, duplicate/rate/resource bounds.
- `audio`, `stt`, `tts`, `turns`: Opus, RMS VAD, adapters, ordered streaming playback,
  cancellation ownership, voice/vision orchestration, user-safe UI notifications.
- `hermes`: public health/capabilities/Responses client, named conversations, stable session key,
  inline image, bounded SSE parser and typed failures. No private Hermes surface exists.
- `control`, `mcp_server`: loopback-only typed control and separate stdio MCP process.
- `captures`, `observability`, `discovery`, `security`: private TTL media, JSON logs, Prometheus,
  doctor, mDNS and token/rate boundaries.
- `simulator`: protocol-faithful device, media E2E, event/fault injection and reconnect backoff.

The Firmware component and thin official HAL adapters implement the frozen
`firmware/stackchan-bridge-client.contract.json`: authentication/hello, bounded protocol and
streams, NVS/USB settings, mDNS/fallback resolution, commands, local state presentation, audio,
camera upload and reconnect. Bridge, MCP and Firmware enforce the source-backed conservative K151
profile of yaw `-45..45` degrees, pitch `5..85` degrees, speed `1..30` (default `15`) and home
`0/45`; the HAL provides the matching local angle envelope. The release build advertises
`head=false` and enables a servo-output lock that blocks position, velocity and torque-enable
writes from remote, local autonomous and app paths; torque-disable remains available. A separately
approved attended candidate disabled that global lock only while the default-on local source lock
rejected avatar/IMU/BLE/app motion and local torque enable. Exact yaw, pitch and home commands
completed with clean physical observations. The candidate was then replaced by a motion-locked
`f73ff28` release with its Wi-Fi diagnostic disabled. The current motion-locked `d88f6df` release
additionally requires six consecutive 50 ms press samples while retaining three consecutive
release/idle samples; its app-only flash, digest, boot and physical no-touch/deliberate-touch
regression are Green. CAM-002 live physical vision turn is PASS.
