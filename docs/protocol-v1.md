# FW–Bridge Protocol v1

Status: **frozen and implemented for v1** (2026-08-29); Bridge/Simulator and Firmware host
contracts are Green, and physical authenticated transport is Green for hello, status/info,
bounded non-motion commands and reconnect. Physical audio and camera media paths are Green;
live-provider-dependent voice and vision acceptance are Green. CAM-002 live physical vision turn
is PASS.

This document is the normative human-readable contract. The JSON Schemas under `protocol/`, the
Bridge Pydantic models, and Firmware constants must remain equivalent. A wire-incompatible change
requires protocol v2; a compatible v1 addition must be optional, bounded, and covered by contract
tests before implementation.

## Transport and fixed limits

| Item | v1 value |
| --- | --- |
| Device endpoint | `GET /v1/device/ws` upgraded to WebSocket |
| Text encoding | UTF-8 JSON object, one object per text frame |
| Maximum JSON text frame | 16,384 bytes, including unknown fields |
| Maximum JSON nesting | 8 object/array levels |
| Binary payload | one raw Opus packet; never JSON or Base64 |
| Maximum Opus packet | 1,275 bytes |
| Logical audio | signed 16-bit PCM, 16 kHz, mono |
| Opus frame durations | 20, 40, or 60 ms; one negotiated value per connection |
| Concurrent streams | one input and one output stream per device |
| Maximum recording | 15,000 ms |
| Handshake timeout | 5,000 ms after WebSocket acceptance |
| Heartbeat interval / pong timeout | 15,000 ms / 45,000 ms |
| Command timeout | default 5,000 ms; allowed range 100–30,000 ms |
| Pending commands | 16 per device |
| Duplicate-ID cache | latest 256 IDs per connection |
| Device connections | 8 by default |
| Capture body / transaction deadline | 2,097,152 bytes / default 10,000 ms (maximum 120,000 ms) |
| Capture status quota | 60 per minute per device, burst 4; separate from uploads |
| Capture rate | 6 per minute per device, burst 2 |
| Non-audio messages | 100 per second per device, burst 200 |
| Diagnostic string | 512 UTF-8 characters |

FW → Bridge binary frames are microphone packets; Bridge → FW binary frames are playback
packets. Start/end text messages establish packet ownership. A binary frame outside the matching
open stream is dropped, counted, and reported as `INVALID_STATE`; it is never guessed or queued
for a future stream. WebSocket ordering is relied upon.

Receivers check the byte limit before decoding JSON. Invalid UTF-8, a non-object root, excessive
nesting, and an oversized frame are `INVALID_MESSAGE`. Three invalid messages within ten seconds
close the connection. Audio packet decode failure is isolated to that stream; three consecutive
Opus failures end the stream with `AUDIO_DECODE_ERROR` and recreate the decoder.

## Envelope

Every JSON message contains:

```json
{
  "v": 1,
  "type": "command",
  "message_id": "c9ef993d-25aa-4f9f-a35d-6441d2f87ee7",
  "sent_at_ms": 0,
  "payload": {}
}
```

Optional routing identifiers are `request_id`, `turn_id`, `stream_id`, and `device_id`. Rules:

- `v` is the integer `1`; booleans, strings, and numeric coercion are rejected.
- All IDs except `device_id` are UUIDs. `sent_at_ms` is an integer from 0 through
  9,223,372,036,854,775,807.
- `device_id` is 1–64 ASCII characters matching `^[A-Za-z0-9][A-Za-z0-9._-]*$`.
- Identity/version strings are non-empty, contain no C0 control characters, and use the bounds in
  their message definition.
- `message_id` is unique within a connection. A duplicate message is not applied twice.
- A duplicate `request_id` with identical command content attaches to/replays the original result;
  different content with the same ID is `INVALID_MESSAGE`. Commands are never re-executed within
  the connection. Firmware retains every executed command result until disconnect, up to 256
  commands and a 256 KiB accounting budget for command text, entry storage, and result text.
  Before executing a new command it reserves room for the maximum-size result. If either limit
  would be exceeded, it reports `INVALID_STATE` and closes for reconnect without executing that
  command or evicting prior results. Disconnect clears the history; callers must not automatically
  retry physical commands across connections because the previous execution outcome may be unknown.
- Unknown extra fields are ignored for forward compatibility but still count toward size, depth,
  property, and string limits. Unknown message types and invalid known enums are rejected.
- Tokens, credentials, raw media, and transcript text are prohibited from envelope metadata.

## Authentication, connection, and close reasons

The WebSocket upgrade requires:

```http
Authorization: Bearer <device-token>
X-StackChan-Device-Id: stackchan-001
```

The Bridge validates the configured device, compares a derived token value in constant time, and
accepts no media or messages before authentication. Within five seconds FW sends `hello`; its
payload `device_id` must equal the authenticated header. Bridge selects the highest mutual version
(v1 currently means exactly `1`) and responds with `hello_ack`. A new authenticated connection for
the same device wins; the old one is closed and all its streams/pending requests are failed before
the new registry entry becomes active.

| WebSocket close code | Meaning |
| --- | --- |
| 4400 | malformed/invalid message |
| 4401 | missing or invalid token |
| 4403 | unknown/disabled device or header mismatch |
| 4408 | hello/heartbeat timeout |
| 4409 | connection replaced by a newer one |
| 4410 | no supported protocol version |
| 4429 | sustained rate/resource limit violation |
| 1011 | internal server failure |

Close reasons are stable, secret-free, and at most 123 UTF-8 bytes. Authentication failures are
distinguished in structured logs without echoing headers or tokens.

Connection state:

Firmware closes and reconnects when its first unanswered heartbeat ping has waited 45 seconds.
Further pings do not extend that deadline; a matching pong clears it. Pong callbacks are delivered
on the polling thread, and callbacks from closed/replaced connections are ignored.

| Current | Input | Next | Required effect |
| --- | --- | --- | --- |
| `UPGRADING` | valid auth | `AWAITING_HELLO` | start 5 s deadline; accept only `hello` |
| `UPGRADING` | invalid auth/device | `CLOSED` | use 4401/4403; create no registry entry |
| `AWAITING_HELLO` | valid compatible hello | `READY` | atomically replace old connection; send ack |
| `AWAITING_HELLO` | timeout/other message | `CLOSED` | 4408/4400 and cleanup |
| `READY` | pong | `READY` | update last-seen time |
| `READY` | pong timeout/socket loss | `CLOSED` | fail streams/commands and unregister by connection ID |
| `READY` | intentional close | `CLOSED` | normal cleanup without retry/error attribution |

## Message catalogue

| Type | Direction | Required routing IDs | Payload |
| --- | --- | --- | --- |
| `hello` | FW → Bridge | none | identity, versions, capabilities, audio |
| `hello_ack` | Bridge → FW | none | connection and negotiated timings |
| `audio.input.start/end` | FW → Bridge | `turn_id`, `stream_id` | audio format / end reason |
| `audio.output.start/end` | Bridge → FW | `turn_id`, `stream_id` | audio format / duration or end reason |
| `command` | Bridge → FW | `request_id`; command-dependent `turn_id` | name and typed args |
| `command_result` | FW → Bridge | `request_id` | exactly one success result or typed error |
| `event` | FW → Bridge | `device_id`; event-dependent IDs | name and typed data |
| `error` | either | IDs of related work when known | typed code, user message, diagnostic detail |

### `hello`

`device_name` is 1–64 characters, `firmware_version` 1–32, `hardware_model` 1–64, and
`protocol_versions` contains 1–8 unique positive integers. Capabilities contain strict booleans for
`microphone`, `speaker`, `camera`, `touch`, `head`, `display`, and `avatar`, plus `led_count` from
0–256. Audio is `codec=opus`, `sample_rate=16000`, `channels=1`, and one supported `frame_ms`.

`hello_ack` contains UUID `connection_id`, `selected_protocol_version=1`,
`heartbeat_interval_ms` in 1,000–60,000, `max_command_timeout_ms` in 100–30,000, and a 1–32
character `server_version`.

### Audio control and stream state

Both start payloads contain the negotiated `codec`, `sample_rate`, `channels`, and `frame_ms`.
`audio.input.start` also contains trigger `touch`, `button`, `wakeword`, `control_api`, or
`simulator`. `audio.output.start.expected_duration_ms` is 0–120,000. End reasons are:

- input: `silence`, `max_duration`, `user_cancel`, `device_error`, `disconnect`;
- output: `completed`, `cancelled`, `barge_in`, `tts_error`, `device_error`, `disconnect`.

Input and output each use this independent state machine:

| Current | Input | Next | Required effect |
| --- | --- | --- | --- |
| `CLOSED` | matching `*.start` | `OPEN` | create a fresh bounded codec/queue context |
| `CLOSED` | binary or `*.end` | `CLOSED` | drop; record/report `INVALID_STATE` |
| `OPEN` | binary ≤ 1,275 bytes | `OPEN` | decode/enqueue for the current stream only |
| `OPEN` | second start | `OPEN` | reject second start; keep original stream intact |
| `OPEN` | matching end | `CLOSED` | drain/flush according to reason, then destroy context |
| `OPEN` | wrong/stale stream ID | `OPEN` | reject/drop without changing current stream |
| `OPEN` | disconnect/cancel/limit | `CLOSED` | discard buffered work and destroy context |

The input maximum is 15 seconds regardless of a missing end message. Playback uses a bounded
queue, detects underflow/overflow, inserts a configurable default 500 ms silent preroll, and
discards all remaining packets on cancel. Audio is never persisted unless privacy debug recording
is explicitly enabled with a TTL.

### Commands

Arguments reject unknown properties. Values are protocol-domain bounds; the configured board
profile may be narrower, and both Bridge and FW must reject values outside that physical profile.
Only local autonomous motion may clamp internally.

| Command | Required `args` and bounds |
| --- | --- |
| `device.get_status`, `device.get_info`, `head.get_angles`, `led.clear` | `{}` |
| `audio.set_volume` | `volume`: integer 0–100 |
| `display.set_brightness` | `brightness`: integer 0–100 |
| `display.show_text` | `text`: 1–256 chars; `duration_ms`: 100–30,000; `priority`: 0–10 |
| `avatar.set_expression` | `expression`: `idle/happy/thinking/sad/surprised/embarrassed` |
| `avatar.set_blink` | `enabled`: boolean |
| `head.set_angles` | `yaw`: number −90–90; `pitch`: number −90–90; optional `speed`: 1–100 |
| `head.home` | optional `speed`: 1–100 |
| `led.set` | `index`: integer 0–255; `r`, `g`, `b`: integer 0–255 |
| `led.set_all` | `r`, `g`, `b`: integer 0–255 |
| `camera.capture` | `capture_id`: UUID; `quality`: integer 10–95; required `timeout_ms`: integer 1–120,000 |
| `camera.cancel` | `capture_id`: UUID; cancels only the matching active capture |
| `speech.cancel` | empty args plus required envelope `turn_id` |

`led.set.index` is additionally less than the authenticated device's `led_count`. A device lacking
the relevant capability returns `INVALID_STATE`. `camera.capture` also requires an outstanding
Bridge-owned capture reservation and one active capture at most.

#### K151 board motion profile

For authenticated hardware model `M5STACK-K151`, the project applies a conservative board profile
inside the wider protocol domain:

| Value | K151 accepted range/default |
| --- | --- |
| yaw | `-45..45` degrees |
| pitch | `5..85` degrees |
| speed | `1..30`; omitted value defaults to `15` |
| home | yaw `0`, pitch `45`, speed default `15` |

The Bridge rejects an out-of-profile K151 command before writing a WebSocket frame, and Firmware
independently rejects it before entering the HAL. The official HAL adapter scales degrees and
speed to tenths and narrows its local servo envelope to the same angles. The release build keeps
`CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y`, advertises `head=false`, and cannot enter that output
path. Therefore this profile is host/build behavior, not evidence of physical motion.

`command_result.payload` is exactly one of:

```json
{"ok": true, "result": {}}
```

```json
{"ok": false, "error": {"code": "INVALID_ARGUMENT", "message": "request rejected"}}
```

Result objects have at most 32 properties. Error messages are user-safe and at most 160
characters; optional diagnostic detail is at most 512 characters and contains no secrets.

### Events

All events are rate-limited and carry their authenticated `device_id`. Bridge ignores any payload
device ID mismatch. Event-specific data is:

| Event | Data |
| --- | --- |
| `touch.tap` | `x`: 0–319, `y`: 0–239 |
| `touch.long_press` | `x`: 0–319, `y`: 0–239, `duration_ms`: 500–30,000 |
| `touch.stroke` | start/end `x/y` in display bounds, `duration_ms`: 1–30,000 |
| `button.press` | `button`: 1–32 chars |
| `wakeword.detected` | optional `confidence`: number 0–1 |
| `battery.changed` | `percent`: 0–100, `charging`: boolean |
| `wifi.changed` | `connected`: boolean, optional `rssi_dbm`: integer −127–0 |
| `audio.underrun`, `audio.overflow` | `stream_id`: UUID, `dropped_packets`: integer 1–65,535 |
| `camera.completed` | `capture_id`: UUID, `ok`: boolean; success requires lowercase SHA-256 `sha256` and `size_bytes` 1–2,097,152; failure carries `error_code` |
| `servo.error`, `device.error` | stable `code`: 1–64 chars, safe `message`: ≤160 chars |

Tap-to-talk is handled locally by FW/Bridge; blink/idle motion is never emitted. Only meaningful
notifications may wake Hermes.

## Protocol errors

Stable error codes are `UNSUPPORTED_VERSION`, `UNAUTHORIZED`, `UNKNOWN_DEVICE`,
`INVALID_MESSAGE`, `INVALID_ARGUMENT`, `INVALID_STATE`, `COMMAND_TIMEOUT`, `DEVICE_BUSY`,
`AUDIO_DECODE_ERROR`, `AUDIO_ENCODE_ERROR`, `CAPTURE_FAILED`, and `INTERNAL_ERROR`.

An error payload separates `message` (short, user-safe, no implementation/secret detail) from
optional `detail` (bounded diagnostics for local structured logs). Error responses never contain a
token, header value, raw payload/media, filesystem path, or conversation transcript.

## Reconnect and compatibility

FW retries abnormal disconnects after 1, 2, 4, 8, 16, then 30 seconds with bounded jitter and a
30-second cap. A connection healthy for 30 seconds resets the backoff. Intentional shutdown does
not schedule retry until configuration/user state allows it. Reconnect creates new connection and
codec contexts; stale socket tasks may not mutate the new registry entry.

v1 receivers ignore bounded unknown fields but never unknown required behavior. Adding an optional
field or event is compatible. Changing meaning/bounds, making a field required, reusing an enum,
or changing binary framing requires v2.

Run `uv run python scripts/validate-protocol.py` after every schema/example change. Contract tests
must prove valid and invalid examples, Schema/Pydantic parity, and Firmware constant parity before
the implementation phase is considered complete.

## Capture transaction protocol 2

Both `hello.payload.capture_protocol_version` and `hello_ack.payload.capture_protocol_version`
are required and equal to `2`. Upgrade Bridge, Firmware and Simulator together. Legacy capture
peers are rejected; the outer envelope and `/v1` URLs remain version 1.

A reservation owns one monotonic deadline starting before command dispatch. A successful
`command_result` acknowledges acceptance. Control returns 201 only when the image is saved and
`camera.completed(ok=true)` provides its matching SHA-256 and byte count. Firmware sends completion
after joining its worker, freeing temporary buffers/connections and releasing camera busy.
Either arrival order is supported; missing command ACK does not override these two proofs.

Before acquiring a frame, Firmware requests authenticated
`GET /v1/device/captures/{capture_id}/status` using the upload credentials. It returns
`capture_id`, `state`, `remaining_ms`, `image_saved`, `expires_at`, `reason`, and, when saved,
`sha256` and `size_bytes`, with `Cache-Control: no-store`. States are `reserved`, `image_saved`,
`succeeded`, `failed`, `cancelled`, `expired`; terminal states never return to an active state.
Firmware uses the request start plus server remaining time, never extending its local deadline.
The final 20% of the command budget (at most one second) is reserved for cleanup and notification.
Receipt queries have a separate per-device quota for initial and recovery checks:
`max(1, 2 * capture_rate_per_minute / 60)` requests/second with a burst of
`max(4, 2 * capture_rate_burst)`. Excess queries return 429 `CAPTURE_STATUS_RATE_LIMITED`
with `Retry-After`; they do not consume the upload quota.

JPEG encoding happens once into bounded PSRAM. Each HTTP operation uses at most three seconds
and the remaining work budget, including DNS, TCP/TLS connection, writes, response reads and close.
Frame dequeue polls in finite slices of at most 20 ms. HTTP runs in the camera worker without a
separate receive task. The shared TCP/TLS transports also reject failed receive-task creation.
There are at most three upload attempts, with 250/500 ms backoff. Transport failures, 408 and
transient 5xx may retry; 501/505 and other errors including redirects are terminal. A 429 retries
only with a positive numeric `Retry-After` that fits the remaining budget. After an ambiguous
upload result, receipt lookup precedes another POST; matching saved proof completes the upload.
An identical duplicate POST by the same owner within the deadline returns the original 201
metadata without rewriting the file or extending retention. Different content is 409, unknown
or cancelled IDs are 404, and expired upload deadlines are 410. Reservation checks precede
upload quota consumption and body reading. Authentication and image validation remain required.

Bridge acknowledges a completion event with `camera.completed_ack`, whose payload is
`{"capture_id":"<UUID>","accepted":true}` (or `false` when the proof is rejected).
Firmware keeps at most 16 pending notifications, retries every 500 ms with fresh message IDs,
and removes an entry on either ACK or deadline. Lost ACKs do not retain camera busy.

Control deadline errors distinguish `CAPTURE_COMPLETION_TIMEOUT` (saved image, no valid completion),
`COMMAND_TIMEOUT` (no command ACK, image or authenticated receipt/upload evidence), and
`CAPTURE_TIMEOUT` (other deadline expiry). Failures use 409 `CAPTURE_FAILED` with bounded
`capture_id`, `stage`, `reason`, and `image_saved` details. When the 1,024 retained transactions
fill Bridge capacity, both capture and vision requests return 429 `CAPTURE_CAPACITY` before
dispatching a camera command. New reservations become available as retention expires.
Cancellation interrupts body reading; late uploads and events cannot reopen a terminal transaction.
Image retention is independently
600 seconds by default; deletion never reopens an upload reservation.
