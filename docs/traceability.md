# Traceability

Every ID in `docs/requirements.md` appears exactly once below. “Firmware host/build Green” is not
a physical hardware PASS. External evidence remains explicit.

| Requirement | Design | Implementation | Unit/contract test | Integration/hardware | Current result |
| --- | --- | --- | --- | --- | --- |
| ARCH-001 | architecture, ADR-0001 | package boundaries + FW/HAL overlay | package/config/secret contracts | Simulator uses only public boundaries; physical authenticated FW↔Bridge wire, loopback-only live Hermes API, local faster-whisper, full physical voice and physical vision turns exercised | Green / live Hermes, STT, physical full voice and CAM-002 physical vision Green |
| PROTO-001 | protocol-v1, state machines, ADR-0002 | schemas + Pydantic + FW parser/guard | protocol models + FW C++ tests | real host and physical WebSocket exchanges | Green: 11 valid/8 invalid; physical hello/status/info Green |
| PROTO-002 | protocol auth/ownership tables | Gateway/Registry/Simulator + FW session, remote-error consumption and RFC-bound WebSocket response validation | gateway/auth/duplicate/send-race + FW session/handshake/error-parser tests | physical authenticated handshake/command/reconnect plus bounded wrong-token rejection/recovery; handshake validation is CI-build Green, while newer send-race and remote-error handling is host-test Green | Host and physical transport/auth-rejection recovery Green / review hardening host-test Green / physical recheck pending |
| FW-001 | upstream baseline, ADR-0006 | vendor snapshot + lock/verifier + overlay | provenance/contract | baseline + integrated `idf.py build`; stable custom boot | Build/boot Green |
| FW-002 | state machines/FW contract | BSP/HAL + service/settings/mDNS/provisioning/display + label-free touch counter and debounced head input; authenticated head-press publication and explicit audio input ownership release on playback/error | state/settings/discovery/provisioning + NVS-key-limit/toast-init/touch-metric/expression-init/head-touch/event/session/error-parser tests | initial correction evidence plus later `d88f6df` six-sample press filter; app-only flash/digest/boot, 60-second no-touch and one deliberate-touch lifecycle Green; newer event and audio ownership changes are host-test Green but have not been flashed | Host/build/network/display/expression/touch Green / correction flashed / no-touch regression Green / deliberate direct touch-to-audio lifecycle Green / audio ownership recovery host-test Green / physical recheck pending / HW-02 PASS |
| FW-003 | ADR-0004/0005, FW contract | audio/camera/command HAL + deferred camera worker + decode-generation cancellation isolation + main-task shutter-audio handoff + K151 profile enforcement + release servo-output lock + attended local-command lock | command/audio/camera/playback-completion/servo-output, motion-profile and command-source safety tests | safe non-motion commands acknowledged; brightness/LED/happy eyes visible; corrected fixed Japanese audio output heard; volume 85 confirmed louder than 45; first physical playback cancelled before a distinct new turn; authenticated physical camera capture/upload/store/TTL lifecycle completed; K151 candidate build/flash/digest/boot Green; exact `yaw=10` moved slightly left, exact `pitch=40` moved down, and final `head.home` moved upward once to measured home without abnormality/contact | Host/build/brightness/LED/expression Green / fixed Japanese audio output Green / comparative volume Green / physical cancellation/new-turn Green / physical camera Green / K151 yaw-pitch-home Green / HW-04 PASS |
| FW-004 | reconnect/flash docs | FW session/reconnect with shared disconnect/error cleanup + bounded digest-verified backup tool + GET-only transport observer + launcher-independent global reconnect notifications | reconnect/post-handshake-transport-error/session/observer/script/nested-backup/reconnect-presentation tests | HW-01 PASS; final physical observer measured 15,697.6 ms including a 3.0-second hold; no reset/panic/watchdog marker observed; newer malformed-frame recovery is host-test Green | Backup/transport/presentation Green / malformed-frame reconnect recovery host-test Green / physical recheck pending |
| BR-001 | operations/config design | CLI/config/entrypoints | config/package contracts | offline/online doctor mocks | Green |
| BR-002 | protocol/Gateway design | Registry/Gateway/handlers with deadline ownership synchronization and normalized command-send disconnects | gateway/upload/audio/deadline-reuse/send-race tests | real Uvicorn plus physical hello/status/info/reconnect; timed-out audio reuse and command disconnect races are host Green | Green / deadline and send-race recovery host Green |
| BR-003 | architecture/network design | Control/runtime/mDNS/metrics + coordinated signal shutdown | control/runtime/mDNS/signal tests | physical liveness/devices/commands/metrics; two-server Ctrl+C exits 130 without traceback; live Hermes tunnel/readiness, local STT, full voice and vision Green | Green / live full voice and vision Green |
| AUDIO-001 | ADR-0004 | codec/normalize/VAD/input/output/debug store with synchronized deadline notification and one 15-second input limit across Bridge/FW/Simulator | audio/VAD/deadline-reuse/limit/debug/playback/error-recovery tests | Simulator WAV flow, clean 30-frame K151 output, physical short-speech WAV/quality/silence-end, silent maximum-duration stop, cancel-before-new-output, ephemeral local STT and one physical full voice turn; newer deadline, limit and FW ownership recovery is host-test Green | Host, physical audio paths, live local STT and full voice Green / review recovery host-test Green / physical recheck pending |
| AUDIO-002 | ADR-0004, adapter contract | Mock/bounded-streaming HTTP/faster-whisper STT | STT response-limit/doctor/voice tests | full Mock STT voice flow plus three live local Japanese patterns, empty speech and one physical single-turn utterance on `small`/CPU/INT8; bounded HTTP response handling is host Green | Live local STT and physical full voice Green / HTTP response bound host Green |
| AUDIO-003 | ADR-0004, segment rules | bounded-streaming and predecode-limited TTS adapters/pipeline/output + configured Simulator segment grace + Firmware decoder-generation isolation | TTS response/duration/order/policy/timing, delayed-segment and Firmware playback-completion tests | full Simulator playback WAV, intelligible fixed-Japanese K151 playback, clean physical cancel-before-distinct-new-turn and an intelligible live two-segment reply with zero underrun; provider bounds and delayed-segment handling are host Green | Host, fixed physical playback, cancellation and live full voice Green / provider and segment bounds host Green |
| HERMES-001 | ADR-0003 | public Hermes client/readiness + v0.20 nested-capability normalizer in `8cb295e` + bounded readiness JSON/raw SSE bytes and whole-response deadline | client/request/cap/readiness-limit/deadline/oversized-SSE tests | Mock Hermes/Runtime plus authenticated v0.20 health/capabilities, text/Skill turns and one physical vision turn; newer readiness and stream guards are host Green | Host and Live Responses API Green / readiness and response guards host Green / CAM-002 physical vision Green |
| HERMES-002 | SSE/segment/state docs | parser/reset/services/notifiers | error/segment/voice/vision tests | tool-progress Mock SSE plus live text/date/Skill SSE at 2,721/5,665/8,590 ms and physical HW-10 at 12,134 ms to first audio / 20,881 ms total | Host and live text/Skill streaming Green / HW-10 physical full voice Green |
| MCP-001 | architecture/MCP design | stdio server + Control client + background speech | MCP server/client/speech/API/integration/package tests | MCP→ASGI/photo fallback; direct text→configured TTS→idle device Opus; live `/v1/skills` discovery and `skill_view` use | Host Green / live Skill path Green / project MCP ingestion and direct speech hardware check pending |
| CAM-001 | ADR-0005/security | store/coordinator/upload/Control + owned failed-completion propagation in `517011a` + scoped camera stack in `f6f0d2d` + main-task shutter audio in `8ad0489` | capture validation/TTL/auth/failure-event/package/Firmware stack and scheduling contract tests | real Simulator upload plus one authenticated physical 320 x 240 JPEG capture/upload/fetch/TTL purge and one physical unavailable-store failure with no retained media | Host/build Green / `camera.completed(ok=false)` → `CAPTURE_FAILED` physical machine path Green / physical success lifecycle Green |
| CAM-002 | ADR-0005 | vision service/API/Hermes/MCP | vision/control/client/MCP tests | generated JPEG answer plus one consented physical capture→live Hermes→spoken answer→delete lifecycle | Host Green / CAM-002 physical vision Green |
| SEC-001 | security/network docs | validators/tokens/pre-authentication rate and concurrent-scrypt gate/log/report/ignore | auth rate/concurrency/cancellation/config + log/report/secret tests | authenticated Gateway/upload plus physical wrong-token rejection without token/log retention; new shared pre-authentication gate is host Green | Green; physical wrong-token rejection Green; pre-authentication resource bound host Green; LAN `ws://` residual risk |
| SEC-002 | protocol/config limits | Bridge/FW rate, queue, capability, K151 motion-profile bounds and authenticated-Bridge-only candidate lock | rate/limit/capability/FW output/source safety matrices | fault injection; isolated candidate app-only flashed and boot/digest verified; exact positive yaw and decreasing pitch physically Green; final home-only run reached measured 0/45 tolerance with clean fail-closed guards | Host/build Green / K151 candidate flashed / yaw-pitch-home Green / HW-04 PASS |
| OBS-001 | observability design | logs/metrics/doctor, including label-free accepted-touch count and authenticated head-press event publication | logging/control/runtime/touch-metric/doctor + FW event/session/HAL contract tests | ready/metrics ASGI; direct physical head-sensor audio lifecycle Green; new `touch.tap` publication is host/build Green but physical `touch_events_total` increase remains pending until the firmware is flashed and observed | Host/build Green / direct touch path Green / physical touch event and metric pending |
| OPS-001 | Simulator design | device/mock/reconnect/fault CLI with bounded input WAV and configurable output-segment grace | Simulator/mock/delayed-segment tests | real Gateway voice/capture | Green / delayed segment and 15-second input bounds host Green |
| OPS-002 | operations/hardware docs | service/backup/report/smoke scripts, including `head=false` visual mode and GET-only reconnect observer | script/report + visual/reconnect observer tests | verified 16 MiB factory backup; approved app-only reflashes; visual helper safely restored and brightness/LED were seen; corrected expression candidate flashed/digest-verified and happy/idle physically confirmed; final reconnect observer/display Green; factory restore NOT RUN | HW-01/HW-05/brightness/LED/expression Green / current app verified / factory restore unused |
| TEST-001 | AGENTS/gate design | verify-host/CI host | script/CI contracts | 2026-09-06 full host gate | Green: 568 passed, 87.40% coverage; format/lint/mypy/protocol/secrets/audit/doctor Green |
| TEST-002 | fault/ownership plan | integration fixtures | async/fault/race tests | actual Uvicorn/WS | Green |
| TEST-003 | FW/hardware plan | fresh primary-USB/motion-locked build gate/source lock/report | provenance + 25 Firmware CTest including K151 safety, protocol errors and audio ownership recovery | prior integrated locked build and final candidate app-only flash/digest/boot Green; 2026-09-05 host CTest is 25/25 Green, but ESP-IDF is not active and no new image was built or flashed | Prior automated and physical HW-01 through HW-13 Green / CAM-002 physical vision Green / sustained-touch physical regression Green / current review changes host/build-test Green / ESP-IDF and physical recheck pending |
| DOC-001 | docs/ADR plan | README/docs/notices/ADR-0001…0006 | package/script/doc contracts | manual cross-review | Current checkpoint Green |

The 2026-09-05 PR-review hardening gate covered command-send disconnect races, Hermes readiness
and streaming-response bounds, the shared 15-second input limit, delayed Simulator output segments,
Firmware input/playback ownership, malformed-frame reconnect recovery, and Bridge protocol-error consumption. The pinned
`espressif/mdns` 1.11.3 source already makes repeated `mdns_init()` calls idempotent, so the related
review suggestion required no source change. No hardware was flashed or physically revalidated.

The 2026-09-06 follow-up covers three additional review findings. AUDIO-002 now shares one
shielded Whisper model-load task across cancelled callers and retries only after a failed load
finishes. BR-002 keeps handshaking connections unavailable to commands, playback and device
listing until `hello_ack` has been sent. AUDIO-001 retains the locally cancelled output turn/stream
identity so a matching late end is idempotent and cannot stop newer input or playback; unrelated
IDs still fail validation. Each fix was reproduced with a failing regression before implementation.
All 509 Python tests and 25 Firmware host CTests pass. ESP-IDF is not active locally, so the full
Firmware build remains a CI check; no image was flashed or physically revalidated for these fixes.

Two further OPS-001 Simulator findings were reproduced and fixed in the same review pass:
WAV duration and decoded sample counts are checked before decoding, and first/later output
streams have fixed duration-plus-grace deadlines with a 120-second cumulative PCM bound.
Silent or continuously streaming missing-end cases fail without saving partial output. The full
host gate now passes 516 tests at 86.65% coverage. Firmware sources are unchanged from the
successful Host/Firmware CI run on `4ae2403`; physical revalidation remains pending.

The next BR-002/AUDIO-001 follow-up preserves the current input stream after invalid start/end
controls while still reporting and counting violations toward the three-message disconnect limit.
VAD completion now leaves the wire deadline armed; expiration releases both input ownership
records without cancelling an already processing voice turn. Regression tests cover accepted and
rejected VAD utterances, reuse after expiration, and continued packet/end handling after invalid
controls. The full host gate passes 521 tests at 86.80% coverage; Firmware sources are unchanged
from the successful Host/Firmware CI run on `9a50332`.

The following AUDIO-001/PROTO-002/SEC-001 review checks cover empty/oversized Opus packet recovery,
typed playback disconnects for text and binary sends, and system randomness for WebSocket handshake
keys and every data/control frame mask. The new wire-level test compiles the actual modified
WebSocket implementation with the locked upstream headers and checks handshake/text/binary/ping/
pong/close output. The full host gate passes 530 tests at 86.97% coverage and Firmware host CTest
passes 26/26. `verify.sh` reports the missing local ESP-IDF explicitly; current Firmware build
verification remains on CI, and no image was flashed or physically revalidated.

The next AUDIO-001 privacy follow-up purges enabled debug WAV storage for the lifetime of the
Gateway at `min(60, audio.debug_ttl_seconds)` second intervals. Regression tests prove expiration
after startup, retry after a filesystem error, preservation of recent and unrelated files, disabled
storage behavior, and cleanup-task shutdown. The full host gate passes 533 tests at 87.06% coverage.
Firmware sources are unchanged from the successful Host/Firmware CI run on `2d3610e`.

Four further BR-002/HERMES-002/OPS-001 findings were reproduced before their fixes. Control API
speech cancellation now rejects `CAPTURING` with `TURN_CAPTURING` instead of leaving input
ownership inconsistent; tests also prove normal input end/reuse and unchanged processing-turn
cancellation. Text and vision SSE reads stop and close after `response.completed`, even when the
server keeps the connection alive. Simulator playback fails on between-segment disconnects and
all non-`completed` end reasons without saving partial WAV output. The full host gate passes 543
tests at 86.99% coverage. Firmware sources are unchanged from the successful Host/Firmware CI run
on `b4ac8cf`; there was no hardware flash or physical revalidation.

The next PROTO-002/FW-004 and BR-002 follow-up resets both WebSocket handshake event bits
before a fresh TCP handshake, preventing prior success/failure from completing a reconnect.
The real transport wire test covers missing/rejected new responses and later valid recovery.
Bridge also preserves recording ownership on `touch.tap` and `touch.long_press` during
`CAPTURING`, while retaining telemetry and processing/playback barge-in. Regressions verify
normal silent input end and subsequent input reuse. All 545 Python tests pass at 86.94% coverage,
and Firmware host CTest passes 26/26. `verify.sh` completed its host gate and then explicitly
reported missing local ESP-IDF; new Firmware build verification remains on CI. No hardware was
flashed or physically revalidated.

The next HERMES-001/CAM-001 follow-up bounds slow-drip HTTP work with wall-clock deadlines.
Health and capabilities share `hermes.timeout_seconds`; a timeout returns readiness failure and
closes the response. Authenticated capture multipart parsing and file reads share a ten-second
deadline; HTTP 408 / `CAPTURE_UPLOAD_TIMEOUT` closes partial files while permitting a later
valid, rate-limited retry. Regressions cover both readiness endpoints plus slow multipart headers,
body, and file reads. The full host gate passes 550 tests at 87.07% coverage. Firmware sources are
unchanged from the successful Host/Firmware CI run on `518b8a5`.

The next BR-002/CAM-001/CAM-002 follow-up converts the 16-pending-command limit to a dedicated
`CommandQueueFullError` and common Control API HTTP 429 / `COMMAND_QUEUE_FULL` response.
Regressions reproduce the former HTTP 500 through actual command, capture, and vision runtime
paths, preserve existing queued work, clean failed capture/turn reservations, and verify recovery
after a slot becomes available. Error responses do not expose internal exception details. The full
host gate passes 554 tests at 87.29% coverage; Firmware sources are unchanged from the successful
Host/Firmware CI run on `d4339e7`.

The next AUDIO-001/PROTO-002 Firmware follow-up limits playback preroll to the 32-packet
queue (1,920 ms at 60 ms/frame), with runtime validation for all supported frame durations.
Command results are retained for the connection instead of evicted after eight requests. Before
the 256-command or 256 KiB accounting budget is exceeded, new execution stops and the transport
closes for reconnect; no new command executes while that reconnect is pending. Regressions cover
same/new-message-ID retries after 8 and 255 later commands, count/byte limits, and fresh-handshake
recovery. Failing tests preceded both fixes. All 554 Python tests pass at 87.29% coverage and all
26 Firmware host CTests pass. ESP-IDF is not active locally; current Firmware build verification
remains on CI. No image was flashed or physically revalidated.

The next PROTO-002/AUDIO-001/CAM-002 follow-up enforces a 45-second deadline from the first
unanswered Firmware ping; further pings cannot extend it. Wire tests verify matching pong
notifications, bounded observer ownership, polling-thread delivery, closed-connection filtering,
timer wraparound, and recovery after reconnect. A Firmware `AUDIO_DECODE_ERROR` now cancels only
the current playback turn and stops upstream packets without another `speech.cancel` command.
Vision captures are deleted immediately after reading, including read failure, before remote work;
ten persistence/outcome regressions preserve unrelated captures. All 568 Python tests pass at
87.40% coverage and all 26 Firmware host CTests pass. Local ESP-IDF remains unavailable, so the
current Firmware build is a CI check; no hardware was flashed or physically revalidated.

The 2026-09-03 attended motion-candidate preflight adds read-only external evidence to FW-003,
SEC-002, OPS-002 and TEST-003: one free stable serial; verified private factory backup and
factory-identical partition; disabled Secure Boot/Flash Encryption; matching current motion-locked
app digest; valid isolated candidate image/config/app-only mapping; one exact scoped firewall rule;
and zero 8765/8766 listeners. There was no flash write or physical head command; explicit flash
approval remains pending, with physical motion requiring a later distinct approval.

The 2026-09-03 attended motion-candidate app-only flash adds external evidence to FW-003, SEC-002,
OPS-002 and TEST-003: the distinct approval covered only the unique-device preflight, a single
`0x20000` app write, independent digest verification and content-suppressed boot qualification. The
write hash and independent digest both matched; a 35.09-second observation had no fault or serial-
disconnect marker. The scoped firewall rule remains for final Goal cleanup, no physical head
command has been sent, and authenticated capability recheck plus physical motion approval remain
pending.

The 2026-09-03 attended initial K151 motion adds external evidence to FW-003, SEC-002, OPS-002 and
TEST-003. After a Red→Green correction made the smoke helper reject device-`ok=false`, a distinct
approval covered exactly one `head.set_angles` command at `yaw=5`, `pitch=45`, `speed=10`. The
authenticated K151 advertised `head=true`; `motion_commands=1`, command acknowledgement, stable
connection, final IDLE and all-zero fault/input/touch/reset markers were Green. The operator observed
motion, reported no abnormal sound, vibration or heat, and touched neither the device, desk nor
cable. The physical yaw/pitch/home sequence remains incomplete because direction-specific movement
and `head.home` were not established; each further command needs separate attended approval.

The 2026-09-03 attended K151 home attempt adds an explicitly inconclusive result to FW-003,
SEC-002, OPS-002 and TEST-003. A separate approval released exactly one `head.home` command with no
retry or additional motion command. It was acknowledged with `motion_commands=1`, `home_commands=1`,
`angle_commands=0`, stable connection, final IDLE and zero fault/touch/reset markers, but the
no-contact window also contained `input_starts=1`, `input_frames=41`, `input_ends=1`; the fail-closed
classifier returned `machine_valid=false`. The operator did not observe movement because the head
appeared already centered, reported no abnormal sound, vibration or heat, and touched neither the
device, desk nor cable. No input cause or position result is inferred; physical home remains
unestablished and HW-04 stays PARTIAL.

The 2026-09-03 attended K151 positive-yaw observation adds direction-specific physical evidence to
FW-003, SEC-002, OPS-002 and TEST-003. A new distinct approval released exactly one
`head.set_angles` command at `yaw=10`, `pitch=45`, `speed=10`, with no retry or home command. All
pre-command audio/event/serial checks were quiet. The exact command was acknowledged with
`machine_valid=true`, `motion_commands=1`, `angle_commands=1`, `home_commands=0`,
`exact_yaw_commands=1`, stable connection, final IDLE, zero input/touch/fault/reset evidence and no
reconnection. The operator saw the face move slightly to the left when viewed from the front,
reported no abnormal sound, vibration or heat, and touched neither the device, desk nor cable. The
positive yaw direction is physically established; pitch and home remain unestablished and each
requires separate attended approval.

The 2026-09-03 attended K151 return-home observation adds bounded physical evidence to FW-003,
SEC-002, OPS-002 and TEST-003 without promoting the fail-closed machine result. Earlier harness
starts stopped before a motion command while exact-float servo readback, terminal input and a changed
pre-command guard were corrected or rejected safely. After the 52/52-test harness passed all
identity, state, position, audio, event and serial guards, its final armed run released one
`head.home`. The operator saw a rightward return to center, confirmed the centered pose, reported no
abnormality and touched neither the device, desk nor cable. Result collection ended with
`unexpected_error` and `machine_valid=false`; a later stdin-closed read-only probe returned
`position_home=true` and `position_offset=false` without sending motion. Thus physical
return-to-home motion was observed, but machine-valid home completion remains unestablished and
HW-04 stays PARTIAL. Postflight retained one serial, zero listeners/harnesses and the exact scoped
Hyper-V rule for final Goal cleanup.

The 2026-09-03 attended K151 pitch observation adds direction-specific physical evidence to
FW-003, SEC-002, OPS-002 and TEST-003. A new distinct approval released exactly one
`head.set_angles` command at `yaw=0`, `pitch=40`, `speed=10`, with no retry or home command. The
61/61-test harness reported `machine_valid=true`, `motion_commands=1`, `angle_commands=1`,
`home_commands=0`, `exact_pitch_commands=1`, three bounded physical position reads, acknowledged
success, stable connection, final IDLE and zero input/touch/fault/reset/reconnect/backtrace evidence.
The operator saw the head move downward when viewed from the front, reported no abnormal sound,
vibration or heat, and touched neither the device, desk nor cable. The decreasing pitch direction is
physically established; machine-valid home completion remains unestablished, so HW-04 stays
PARTIAL. Postflight retained one serial, zero listeners/harnesses and the exact scoped Hyper-V rule.

The 2026-09-03 attended K151 machine-valid home adds final HW-04 motion evidence to FW-003,
SEC-002, OPS-002 and TEST-003. After a 57/57-test Red→Green home harness and a new distinct approval,
one exact `head.home` command ran from measured pitch 40.3 degrees with no retry or additional
motion. `machine_valid=true`, exact command counts, acknowledgement, stable connection, final IDLE,
three bounded position reads and all-zero input/touch/fault/reset/reconnect/backtrace evidence were
Green. The final position was yaw 0.6/pitch 44.3 degrees, inside the configured 0/45 ±2-degree home
neighborhood. The operator saw one upward movement, reported no abnormality and no contact, but did
not independently resolve the fine final angle by eye; the bounded readback supplies that evidence.
Postflight retained one serial, zero Windows/WSL listeners and harnesses, default inbound Block and
the exact one scoped Hyper-V rule for final Goal cleanup. Thus machine-valid home completion is
established, K151 yaw-pitch-home Green is traceable, and HW-04 is PASS. Historical inconclusive and
fail-closed home observations remain unchanged.

The automated side of TEST-003 is Green: `verify.sh` builds a fresh Bridge-enabled,
primary-USB/servo-output-locked custom image and rejects a generated config without those required
settings. HW-01 is Green on one uniquely identified K151 with a verified factory boot log,
partition table and 16 MiB backup. Red→Green corrections cover provisioning boot, interactive USB
input, ESP-IDF's NVS key limit, null-free command envelopes, the K151 wire identity, safe global
toast initialization and expression-time avatar initialization. The current app is flash-verified;
physical Wi-Fi, authenticated hello/status/info, display, brightness, LED and restart/reconnect
presentation are Green. The expression correction was subsequently written app-only and
digest-verified; an attended expression-only run physically confirmed happy and idle restoration
with stable zero-error metrics. The final reconnect observer
measured 15,697.6 ms including its deliberate 3.0-second down hold; simultaneous serial evidence
contained no reset/panic/watchdog marker and the operator saw both toasts. `e73dc30` established
the global path, while `7913742` removed its launcher avatar-initialization dependency. The lower
toast-stack placement remains recorded. The corrected Unicode-built fixed Japanese candidate was
machine-recognized before all 30 Opus frames completed on the K151; the operator reported it
properly audible, state returned to IDLE and volume/error counters restored cleanly. A single
no-touch comparison later restored volume and state cleanly but emitted one input start/end pair;
the operator confirmed no contact. The new startup-qualified three-sample debouncer passes 19
Firmware CTest targets and a fresh ESP-IDF build; its retained `fffaba3` app-only write, independent
digest and clean boot are Green. A separately consented authenticated observation then stayed stable
for 60.03 seconds; the operator confirmed touching neither the device, desk nor cable, and
audio-input start/end, frames, discarded bytes and device events all remained zero. The corrected
no-touch regression is physically Green. A second consented connection stayed stable for 51.11
seconds while the operator performed one approximately one-second touch/release without speaking;
one touch-to-silence lifecycle delivered 25 frames / 3,617 bytes that were immediately discarded.
This makes HW-02 PASS. A distinct consented session then reconstructed and validated private WAVs:
short speech passed volume/noise/VAD and ended for silence, while an intentionally silent held-touch
path stopped for maximum duration. Both were immediately deleted without replay, transcription or
external processing, making HW-07 PASS. Source commit `e824ef4` then passed 20/20 Firmware CTest,
app-only write/digest/boot verification and an attended cancellation run. The first audible stream
stopped short, a distinct second stream played after a gap, every final queue/device/input counter
was zero and the operator confirmed no contact; physical cancellation/new-turn Green makes HW-11
PASS. A subsequent bounded silent/440/880 comparison completed six stable no-contact phases with
zero input/touch/error evidence; the operator heard only the two expected 880 Hz tones. This makes
the input-safety follow-up Green while retaining the earlier event as unexplained intermittent
history. At that checkpoint, the one approved narrow firewall rule was retained until final Goal
cleanup; default inbound was Block, no Bridge process or listener remained and USB was attached
for the next approved hardware check.
For the camera slice, source commit `8bfc589` moved worker startup after command-result delivery;
the one consented physical request confirmed that ordering but ended before capture/upload
completion. Commit `517011a` then added ownership-safe `camera.completed(ok=false)` propagation as
`CAPTURE_FAILED` and restored the capture production package to version control. This is diagnostic
traceability only. A second separately consented request ended after 45,227 ms at
`device_reconnected_or_disconnected`, with `capture_completed_events=0`, no upload and no retained
media. The single capture/JPEG/HTTP worker had ESP-IDF's 3,072-byte default stack; a failing contract
preceded `f6f0d2d`, which scopes 12 KiB to that worker and restores the caller configuration. The
missing simultaneous serial trace means this does not prove stack exhaustion. No image was displayed, viewed, externally processed or retained.
The retained source commit `64062cd` app at
`firmware/build-hermes-hw12-stack-64062cd/stack-chan.bin`, containing `f6f0d2d`, passed its complete
preflight, explicitly approved `0x20000`-only write, independent read-only digest and a 16,037 bytes
single-reset clean boot with zero panic/watchdog/assert markers. HW-12 remains NOT RUN because this
is prerequisite evidence, not capture/upload evidence. One separately consented
post-stack diagnostic then sent one command without retry and ended after 45,091 ms at the unchanged
`device_reconnected_or_disconnected` stage with `capture_completed_events=0` and no upload. The
12 KiB mitigation did not resolve the physical failure. No image was displayed, viewed, externally processed or retained.
HW-12 remains NOT RUN; cause-discriminating diagnostics must precede any further newly consented
physical attempt and fresh explicit camera consent remains mandatory.
A later separately consented content-free serial diagnostic ended after 45,016 ms with
`panic_observed`, one boot/reset window and no camera frame-copy/error marker, completion or upload.
This is consistent with a panic before the existing frame-copy marker, but the deliberately bounded
aggregation does not identify the exact panic site. No image was displayed, viewed, externally processed or retained.
HW-12 remains NOT RUN pending a Red stage-boundary contract and the smallest diagnostic or fix.
A subsequent separately consented content-free backtrace diagnostic sent one command without retry
and ended after 45,020 ms with no completion or upload. Retained-ELF classification of
nine bounded code addresses was `shutter_audio_path`; the one panic/reset window and missing frame-copy/error
markers narrow the observed failure to shutter-sound playback before camera dequeue/frame copy.
The bounded evidence does not identify the exact faulting instruction. It retained no
exact addresses, raw symbols or raw serial. No image was displayed, viewed, externally processed or retained.
At that checkpoint HW-12 remained NOT RUN pending a Red shutter-audio boundary contract and the
smallest correction; another physical camera request still required fresh explicit privacy consent.
The Red contract and main-task shutter-audio correction are now complete in `8ad0489`. Its retained
candidate passed final source/build gates, explicit app-only flash, independent read-only digest and
three consecutive clean boot windows after one transient FreeRTOS stack-overflow did not reproduce.
That transient remains unexplained. There was no camera command during these prerequisites. No image was displayed, viewed, externally processed or retained.
At that prerequisite checkpoint, HW-12 remains NOT RUN and exactly one content-suppressed retry
required fresh explicit camera consent. The successful post-correction HW-12 capture then used
fresh explicit privacy approval for exactly one camera command with no automatic retry. The authenticated storage lifecycle completed with
`local_capture_green=true`, `machine_valid=true` and `serial_camera_frame_markers=1`, then purged all
media. The operator reported that the shutter sound was not heard and no screen change was seen.
No image was displayed, viewed, externally processed or retained. Postflight kept USB attached and
the scoped firewall rule for final cleanup while leaving no listener or media. This makes
HW-12 camera PASS and CAM-001 physical lifecycle Green. At that checkpoint CAM-002 live
`input_image` remained pending; the later accepted vision turn completed it.
The successful HW-13 wrong-token recovery used an authenticated baseline followed by one bounded
mismatch phase. The accepted repeat recorded `wrong_auth_failures=5.0`,
`wrong_phase_registered=false`, `recovery_elapsed_ms=26890` and `final_state_idle=true` with no camera, audio or actuator command.
The first attended run supplied the `Connecting Bridge` observation; after its recovery toast was
missed, a separately approved repeat supplied `Bridge connected` with no operator contact.
No token or raw serial was displayed or retained in host evidence. Postflight left USB attached, no listener
or harness, and the scoped firewall rule retained for final Goal cleanup. This makes
HW-13 wrong-token recovery Green; the later Hermes-stop evidence follows below.
The successful HW-13 Hermes-stop recovery used local Mock Hermes through the production public HTTP/SSE client
with the production Gateway, voice-turn service, notifier and audio streamer. A single deliberate
stop produced `failure_error_code=HERMES_FAILED`, `failure_notification_successes=1`,
`failure_audio_frames=0.0` and `failure_turn_released=true`. The first diagnostic yielded a blank Japanese toast
because `lv_font_montserrat_20` lacks the selected glyphs and an inaudible 440 Hz recovery; it was
rejected before TDD corrections and a separately approved repeat with no automatic retry.
The accepted run displayed `HERMES OFFLINE`; its recovery had `recovery_probe_ready=true`,
`recovery_turn_completed=true`, `recovery_output_streams=1`, `recovery_audio_frames=20.0`,
`recovery_elapsed_ms=35` and `recovery_device_idle=true`. The operator heard one 880 Hz recovery tone,
saw no other screen change and confirmed no physical contact. There was no camera, microphone or actuator command
and only one bounded recovery audio stream. The observer discarded 1,412 serial bytes with
zero input, touch, queue and device-error events and zero boot, panic, watchdog, stack, heap, brownout and reset markers.
Postflight had no listener/harness; Windows reported USB attached and the scoped firewall rule retained,
while WSL serial enumeration was absent. HW-13 Hermes-stop recovery Green is local contract evidence;
live HW-09 remains NOT RUN, and TTS stop, temporary Wi-Fi loss and camera-failure evidence remain.
The successful HW-13 TTS-stop recovery used a 13-test temporary harness and a local HTTP WAV provider
through the production TTS adapter `GenericHttpWavTtsAdapter`; local Mock Hermes stayed ready.
After `tts_baseline_ready=true`, one attended TTS stop produced `failure_error_code=TTS_FAILED`,
`failure_notification_successes=1`, `failure_audio_frames=0.0` and `failure_turn_released=true`.
The operator read `TTS OFFLINE`, reported no abnormal screen change and confirmed no physical contact.
There was one TTS stop phase and no automatic retry. Provider recovery produced `tts_stop_phases=1`,
`recovery_tts_ready=true`, `recovery_turn_completed=true`, `recovery_output_streams=1`,
`recovery_audio_frames=20.0`, `recovery_elapsed_ms=35` and `recovery_device_idle=true`.
The operator heard one 880 Hz recovery tone. There was no camera, physical microphone or actuator command
and only one bounded recovery audio stream. The observer discarded 23,728 serial bytes with
zero input, touch, queue and device-error events and zero boot, panic, watchdog, stack, heap, brownout and reset markers.
Postflight found one free serial device, USB attached, no listener on 8765/8766/18767/18768,
no harness and the scoped firewall rule retained. HW-13 TTS-stop recovery Green is local production-adapter evidence;
At that TTS-stop checkpoint, live HW-10 was NOT RUN, and temporary Wi-Fi loss and camera-failure
evidence remained.
The successful HW-13 camera-failure recovery used a 21-test temporary harness with pytest, Ruff,
format and strict mypy Green. Fresh explicit privacy approval covered exactly one camera command
and no host-side retry through the production `CaptureCoordinator`, `CaptureStore`, Device Gateway
and Control API. The Gateway used `capture_store=None`, and the contract proved rejection before
request form/body parsing. The physical command reached `serial_camera_frame_markers=1`; three
bounded Firmware upload attempts produced `capture_store_unavailable_responses=3`, followed by
`capture_completed_events=1`, `capture_completed_ok=0` and `failure_event_forwarded=true`.
Control returned `control_status=409` and `control_error_code=CAPTURE_FAILED` after
`elapsed_ms=505`. Ownership cleanup recorded `reservations=1`, `reservation_cancels=1`,
`capture_total=0.0`, `files_remaining=0` and `temporary_directory_removed=true`. The connection
completed `status_commands=2` and `final_state_idle=true` with no audio or actuator command. The
observer discarded 2,924 serial bytes with zero input, touch, queue and device-error events and zero
camera-error, boot, panic, watchdog, stack, heap, brownout and reset markers. The host did not
inspect the media, and no raw image bytes, exact image hash or capture ID were displayed or retained.
The operator reported no shutter sound and no physical contact; screen presentation was not
observed, so no physical display claim is made. Postflight found one free serial device, USB
attached, no listener on 8765/8766/18767/18768, no harness and the scoped firewall rule retained.
HW-13 camera-failure recovery machine Green is traceable through CAM-001 and TEST-003. At that
camera-failure checkpoint, HW-13 was PARTIAL solely because temporary Wi-Fi loss was NOT RUN.
HW-02 and HW-04 are PASS; comparative volume and the bounded K151 yaw/pitch/home sequence are Green.
The successful HW-13 Wi-Fi-loss recovery used a 19-test temporary harness with pytest, Ruff,
format and strict mypy Green. Source commit `3f3ee40` produced a 3,921,040-byte diagnostic image,
SHA-256 `137d140de9f4279c86654949307003dfb6d216648e923cc84130057cd1acf4f3`, retaining the physical
motion lock. It was written only at `0x20000`; its esptool write hash, independent read-only digest
and clean 30-second boot passed. The attended run recorded `wifi_cycle_commands=1`,
`cycle_duration_seconds=15`, `cycle_start_acks=1`, `cycle_restart_acks=1`,
`websocket_disconnects=1.0`, `recovery_connection_replaced=true`,
`recovery_elapsed_ms=11329`, `recovery_idle=true` and `recovery_wifi_connected=true`.
There was no camera, audio or actuator command. The observer discarded 1,286 serial bytes with
zero input, touch, queue and device-error events and zero boot, panic, watchdog, stack, heap,
brownout and reset markers. The operator saw `Connecting Bridge` and `Bridge connected`, reported
no abnormal movement or sound and confirmed no physical contact. The 3,920,800-byte normal image
from source commit `3f3ee40`, SHA-256
`32988d0d66eea2a44e690c1b593182b411f1b1408c23eeb2d0aa59a59aca7e71`, was then written only at
`0x20000`; its esptool write hash, independent read-only digest and clean 30-second boot passed,
leaving the diagnostic feature disabled. This makes HW-13 Wi-Fi-loss recovery Green and completes
HW-13 as PASS through TEST-003.
At that HW-13 checkpoint, HW-06, HW-07, HW-08, HW-09, HW-11, HW-12 and HW-13 were PASS while
HW-10 remained NOT RUN; the later HW-10 and CAM-002 evidence above completed those boundaries.
Live local STT Green was established with three ephemeral Japanese patterns and an empty-speech
case through the production `small`/CPU/INT8 faster-whisper adapter; no audio was retained.

Final Goal cleanup is complete. The scoped Hyper-V rule, USB attachment, temporary Bridge/TTS and
Hermes connectivity, control socket, harnesses and Goal-owned temporary artifacts were removed
after evidence commit `a49adc8`; the final audit is recorded in the hardware and verification
reports.
