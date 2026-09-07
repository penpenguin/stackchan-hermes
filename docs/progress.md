# Progress

Last updated: 2026-09-04 (Asia/Tokyo)

Status: all safe host-side, Simulator, Mock Hermes and MCP work plus the integrated custom
Firmware implementation/build are complete in this environment. Exactly one K151/CoreS3 was
identified and its pre-flash boot, security, partition table and verified 16 MiB factory backup
complete HW-01. The approved motion-locked custom Firmware is flashed; interactive USB
provisioning, bounded physical NVS writes, Wi-Fi, authenticated Bridge hello and status commands
plus independently observed global display and reconnect notifications are Green. HW-03 and HW-05
are PASS. The corrected input path passed both an attended no-touch regression and one deliberate
touch/release observation, so HW-02 is PASS. HW-04 now has physically visible brightness and blue
LED effects. The flashed app's happy-expression false success was reproduced, fixed in `421457b`,
written as an approved app-only update, independently digest-verified and physically confirmed.
This makes expression physically Green. The later identical-stimulus volume comparison was also
confirmed: the second volume-85 play was clearly louder than the first volume-45 play. Comparative
volume is Green. One separately approved initial bounded head command was also physically observed
without abnormality. Later exact positive-yaw and decreasing-pitch commands were independently
observed moving left and down from the operator's front view with clean machine evidence. A final
separately approved home-only run moved upward once and measured pitch `40.3° → 44.3°` within the
configured home tolerance. Machine-valid home completion is established, so HW-04 is PASS.
HW-06 PASS:
the corrected fixed Japanese source completed physical Opus playback and was properly audible with
clean counters, IDLE return and volume restoration. The earlier
motion-locked `7913742` app's controlled restart recovered in 15,697.6 ms
including a deliberate 3.0-second hold, without serial reset/panic/watchdog markers, and the
operator saw both reconnect toasts. HW-07 physical audio input and HW-11 physical cancellation are
PASS. HW-12 physical camera capture/upload and HW-13 failure handling are PASS. HW-09 live Hermes
Responses API is PASS. HW-08 live local faster-whisper STT is PASS. HW-10 live physical full voice
turn is PASS. CAM-002 live physical vision turn is PASS.
HW-13 combines wrong-token,
local-public-contract Hermes-stop, HTTP-WAV TTS-stop, camera-failure and attended device-local
Wi-Fi-loss recovery Green. The device was restored to the motion-locked normal release afterward.
The live HW-09 run reached the loopback-only Hermes v0.20.0 API on a private local host through
authenticated SSH forwarding. Its nested `features`/`endpoints` capability document first reproduced
the Bridge's flat-schema incompatibility, then passed after the TDD correction in `8cb295e`. Live Bridge
readiness was fully Green. The three required Responses/SSE turns completed in 2,721 ms, 5,665 ms
and 8,590 ms; the date answer was correct, and the explicit `ascii-art` question emitted two
`skill_view` calls with the requested Skill reference. On the Bridge side, the API key remained
process-only and was neither printed nor stored. The post-correction `./scripts/verify-host.sh` was Green with
432 tests passed in 32.32 seconds and 85.26% coverage; the subsequent evidence-contract gate had
433 tests passed in 35.02 seconds at 85.32%.
The live local HW-08 run used the production faster-whisper adapter with the locked `small` model on
CPU/INT8. A pre-existing Mac `Kyoko` voice supplied three ephemeral 16 kHz mono samples: `こんにちは`
was recognized exactly in 3,689 ms, `今日の日付を教えて` exactly in 2,150 ms, and
`スタックチャン、元気ですか` as the semantically equivalent `スタックちゃん、元気ですか?` in
2,238 ms. One second of all-zero PCM returned empty in 10,961 ms. Each remote temporary AIFF was
removed immediately, samples remained process-only, and no audio retained. This is provider
acceptance; the later HW-10 run completed the physical microphone-to-speaker turn.

The first separately consented full-voice candidate exposed a historical duplicate-turn and
underrun finding: one physical contact produced 112 input frames, 121 output frames, one STT, one
Hermes request, two TTS segments, two turn outcomes and five playback underruns. Failing tests
preceded `9f42b92`, which requires stable idle before touch re-arm, and `f73ff28`, which paces
output against absolute monotonic deadlines. Their full gate and retained motion-locked app passed
before an app-only flash, independent digest verification and clean boot observation.

HW-10 live physical full voice turn is PASS. On 2026-09-04, one fresh microphone consent covered
one head touch and `今日の日付を教えて`, with no retry. The final run accepted 63 input frames, sent
129 output frames, and recorded one STT, one Hermes and one completed turn plus two TTS segments.
There were zero connection, disconnection, underrun, overflow, decode, auth and timeout deltas;
the device returned idle with no camera or motion use. The operator heard and understood the answer
and reported no `Connecting Bridge` toast, abnormality or additional contact. No recording was
retained.

CAM-002 live physical vision turn is PASS. One fresh camera consent covered one capture, one live
Hermes vision request and one spoken response, with no automatic retry. The lifecycle recorded
`capture_total +1`, 100 output frames, a successful response, DELETE returned 204 and
`files_remaining=0`; the host neither displayed nor retained the JPEG. The operator heard and
understood the answer, confirmed that its description matched the camera scene, and reported no
`Connecting Bridge` toast, unexpected display change, physical contact or abnormality. A separate
unsolicited turn immediately before the accepted vision turn contained one no-contact input frame
and no STT request; it is not part of the CAM-002 success claim.

The earlier three-sample correction remains valid historical HW-02 evidence, but it did not reject
that shorter CAM-002-window burst. A new Red test therefore required six consecutive 50 ms press
samples while preserving three consecutive release/idle samples. Source commit `d88f6df` passed
438 tests at 85.45% coverage and 22/22 Firmware CTest before its fresh ESP-IDF build. The retained
motion-locked image is
`firmware/build-hermes-touch-filter-d88f6df/stack-chan.bin`, 3,920,848 bytes, SHA-256
`32ec714f11a7c906e6ff73f3c7813f3ed5a0fb06328df1b6db0acba1ae54d881`. Its app-only write,
independent digest and clean content-suppressed boot passed; the observer discarded 13,251 serial
bytes without a boot, reset or fault marker. In the separately consented physical regression, the
60.000-second no-touch window produced no input lifecycle. One intentional approximately one-
second touch then produced exactly one lifecycle with 20 Opus frames and 2,878 bytes, followed by a
10.001-second post-touch quiet window. All content was discarded and the operator confirmed no
speech, screen change, other contact or abnormality. The aggregate reported
`connection_stable=false`; because setup timing was not retained, that auxiliary value is not used
as connection-stability evidence. Sensor acceptance instead rests on the bounded input counts and
operator observation; HW-05 independently supplies connection-reliability evidence.

The final documentation full gate completed with 439 tests passed in 32.52 seconds at 85.45%
coverage, 22/22 Firmware CTest, locked-dependency verification and a clean ESP-IDF v5.5.4 build.
Its temporary 3,920,848-byte verification image had SHA-256
`fb4193c340c29fc9e5861b81de85a113da91bedd96969ab3d44a7550873f09ac`; it is build evidence and
was not flashed.
A no-touch HW-04 volume comparison then played identical 25-frame beeps at 45 and 85, restored 70
and stayed IDLE/error-free, but emitted one unsolicited audio-input start/end lifecycle. The
operator confirmed touching nothing and no content was retained. Commit `e19098d` adds a TDD-built
`HeadTouchDebouncer` that requires a stable idle baseline and three consecutive samples per
transition; 19/19 Firmware CTest and a fresh ESP-IDF build are Green. The retained app was
subsequently flashed only at `0x20000`, independently digest-verified
and observed through a clean 30-second boot. A separately consented observer then held one
authenticated connection for 60.03 seconds. The operator confirmed touching neither the device, desk nor cable.
Across the full window, audio-input start/end, frames, discarded bytes and device events all remained zero.
The no-touch regression is physically Green. In a separately consented follow-up, one authenticated
connection remained stable for 51.11 seconds. The operator confirmed one approximately one-second touch/release and no speech.
One touch-triggered lifecycle ended for silence; 25 Opus frames and 3,617 bytes were counted and immediately discarded.
No content was saved, printed, replayed, transcribed or analyzed. At that checkpoint HW-02 was PASS
while HW-07 remained NOT RUN because no WAV, quality or maximum-duration stop was assessed. A later
separately consented session completed HW-07: short speech delivered 68 Opus frames / 9,946 bytes
over 4.08 seconds, reconstructed and reopened a private WAV, measured SNR 24.1991 dB and accepted
400 ms before ending for silence. An intentionally silent held-touch run delivered
248 Opus frames / 36,329 bytes over 14.88 seconds and stopped for maximum duration.
The operator confirmed approximately 20 seconds of touch, no speech and a final release.
Both files were mode `0600` and immediately removed (`wav_deleted=true`), with
`private_files_remaining=0` and `hw07_green=true`. There was no replay, transcription, external
service, cloud service or Hermes processing.
For HW-11, failing Firmware tests preceded physical-completion commit `5bcabc8` and decode-
generation isolation source commit `e824ef4`. The retained
`firmware/build-hermes-hw11-e824ef4/stack-chan.bin` is 3,919,184 bytes with SHA-256
`6167fec5380d78fbc6026d6a931169e1f39d0dd5eef12a9897a84f393860cfec` and 24% app free. Its
source checkpoint had 363 tests passed. Its approved app-only write, independent digest and clean
30-second boot passed. Rejected diagnostics
proved that isolated 440 Hz was physically inaudible and separately surfaced a no-contact input
lifecycle; no content was retained. The accepted 880/880 Hz attended run had zero queue/device/
input errors, cancelled the first physical sound, entered `SPEAKING` for a distinct new turn and
returned IDLE. The operator heard a short first beep and longer second beep without contact.
For HW-12, source commit `8bfc589` moved camera work behind the command-result send. Its retained
`firmware/build-hermes-hw12-8bfc589/stack-chan.bin` is 3,919,344 bytes with SHA-256
`319006f5c9aa0ed06eb2de906c3da43a1aa022c9606789e816b0044124d6cd60`. The explicitly approved
app-only write and independent digest passed; a content-suppressed boot observation captured
12,627 bytes with expected boot markers and no panic/watchdog/assert marker. One separately
consented bounded camera request then advanced from the predecessor's five-second
`COMMAND_TIMEOUT` to a 45-second `CAPTURE_TIMEOUT`, proving only that command-result ordering was
corrected; it did not prove capture or upload. No image was displayed, viewed, externally processed or retained.
A new failing Bridge test showed that `camera.completed(ok=false)` was ignored while the capture
store waited. Commit `517011a` now propagates that event as `CAPTURE_FAILED`, validates device
ownership, and ensures the previously ignored capture source package is tracked. Its source
checkpoint host gate was Green with 369 tests passed and 85.26% coverage. A second separately
consented single request then ended after 45,227 ms at `device_reconnected_or_disconnected`, with
`capture_completed_events=0`, no upload and no retained media. Static inspection found the whole
capture/JPEG/HTTP path on one 3,072-byte default-stack worker. Commit `f6f0d2d` gives only that
worker a scoped 12 KiB stack, but the absent simultaneous serial trace does not prove stack exhaustion.
No image was displayed, viewed, externally processed or retained. HW-12 remains NOT RUN after the
retained source commit `64062cd` candidate containing `f6f0d2d`,
`firmware/build-hermes-hw12-stack-64062cd/stack-chan.bin`, 3,919,712 bytes with SHA-256
`f984c5181a48a3cf86a97f9cac59c0584d7c4eeb8a4ad8b81226c972f0cf92a6`, passed its
`0x20000` app-only flash, independent read-only digest and clean boot verification. Its accepted
16,037 bytes observation had one each of the ROM/reset/project/version markers and zero
panic/watchdog/assert markers. The candidate evidence host gate was Green with 373 tests passed in
30.01 seconds. One fresh
approval then authorized one post-stack diagnostic. It sent exactly one camera command with no
automatic retry and ended after 45,091 ms at the same `device_reconnected_or_disconnected` stage,
with `capture_completed_events=0`, `connection_stable=false` and no upload. The 12 KiB mitigation did not resolve the physical failure. No image was displayed, viewed, externally processed or retained.
Cleanup left zero owned capture media. HW-12 remains NOT RUN, and a bounded cause-discriminating
diagnostic must precede fresh explicit camera consent for any further camera attempt. The post-stack
evidence host gate was Green with 374 tests passed in 28.12 seconds at 85.20% branch coverage.
A later fresh approval authorized one content-free serial diagnostic. It sent exactly one camera
command with no automatic retry and ended after 45,016 ms at the same network failure stage, but
the serial evidence now classified the device outcome as `panic_observed`. The one boot/reset
window had `serial_panic_markers=2`, `serial_boot_markers=1`, `serial_reset_markers=1`,
`serial_camera_frame_markers=0`, `serial_camera_error_markers=0`,
`serial_brownout_markers=0`, `serial_watchdog_markers=0`, `serial_stack_markers=0`, and
`serial_heap_markers=0`. This is consistent with a panic before the existing frame-copy marker,
but the aggregation does not identify the exact panic site. No image was displayed, viewed, externally processed or retained.
Postflight left zero owned capture media. HW-12 remains NOT RUN pending a tested stage-boundary
diagnostic or minimal correction. The content-free serial evidence host gate was Green with
375 tests passed in 28.01 seconds at 85.20% branch coverage.
A further fresh approval authorized one content-free backtrace diagnostic after its temporary
harness passed 36 tests plus Ruff and strict mypy. The harness sent exactly one camera command with
no automatic retry and returned HTTP 504 `CAPTURE_TIMEOUT` after 45,020 ms at
`device_reconnected_or_disconnected`, with zero completion, capture, upload, input and touch events.
The observer discarded 13,726 serial bytes and recorded `serial_backtrace_addresses=9`,
`serial_panic_markers=2`, `serial_boot_markers=1`, `serial_reset_markers=1`,
`serial_camera_frame_markers=0` and `serial_camera_error_markers=0`; brownout, watchdog, stack and
heap markers were also zero. Retained-ELF symbolization classified the nine bounded code addresses
as `shutter_audio_path`. Combined with the missing frame-copy marker and the static call order, this
narrows the observed panic to the shutter-sound playback path before camera dequeue/frame copy, but
the bounded classification does not identify the exact faulting instruction. It exposed or retained
no exact addresses, raw symbols or raw serial. No image was displayed, viewed, externally processed or retained.
Postflight again found zero owned capture media, a free serial device, no WSL/Windows listener, USB
attached and the one scoped firewall rule intact. HW-12 remains NOT RUN pending a failing
shutter-audio boundary test and the smallest correction before any newly consented physical retry.
The content-free backtrace evidence update's complete host gate was Green with 376 tests passed in
30.29 seconds at 85.26% branch coverage; formatting, Ruff, strict mypy, protocol validation, secret
scan, dependency audit and offline doctor also passed.
The main-task shutter-audio correction in `8ad0489` followed a failing Firmware contract: the
camera worker now schedules the shutter sound through `Application::Schedule` instead of entering
the codec/timer/Ogg path directly from the 12 KiB pthread. Final `./scripts/verify.sh` was Green with
377 tests passed in 30.88 seconds at 85.26% branch coverage, all 20 Firmware CTests, source/dependency checks and a
fresh ESP-IDF build. Its temporary 3,919,968-byte gate image had SHA-256
`feda68eb9e682cfafdb9997682addf079fda9617ee860f3fffb9a814b573ad1e` and was removed without flash.
The retained candidate is
`firmware/build-hermes-hw12-shutter-8ad0489/stack-chan.bin`, 3,919,968 bytes, SHA-256
`8b55b48a84e71820456dee68d16a2e73a7eb5ab836a8a3e8bd0638fe4686e296`, with valid image checksum,
validation hash, 24% app-partition headroom, the required Bridge/USB/motion-lock settings and the
factory-identical partition table. Its app arguments are `0x20000`-only.
After separate explicit flash approval, esptool wrote only that app, verified the write hash, and an
independent read-only digest matched. A physical-button monitor attempt was rejected after usbipd
detached before boot markers were captured. The first same-FD serial hard-reset window then saw one transient FreeRTOS stack-overflow
and an automatic reboot; it did not reproduce in three consecutive clean boot windows. Each accepted
35-second window had one boot/reset/project/version marker and zero
stack, panic, watchdog, assert, heap, brownout or disconnect markers. The transient remains
unexplained and is not claimed fixed. There was no camera command during build, flash, digest or boot
qualification. No image was displayed, viewed, externally processed or retained. Postflight left
one free serial device, USB attached, no listener or capture media, and the scoped firewall rule
retained. HW-12 remains NOT RUN until one content-suppressed physical retry receives fresh explicit
camera consent.
The main-task shutter-audio flash evidence host gate was Green with 378 tests passed in 31.48 seconds
at 85.26% branch coverage; formatting, Ruff, strict mypy, protocol validation, secret scan,
dependency audit and offline doctor also passed.
The successful post-correction HW-12 capture then used fresh explicit privacy approval for exactly
one camera command with no automatic retry. HTTP `201` / `200` / `404` covered reservation, fetch
and post-expiry fetch; `capture_completed_events=1`, `capture_completed_ok=1`,
`capture_total=1.0`, `capture_failure_total=0.0`, `local_capture_green=true` and
`machine_valid=true`. The valid 4,948-byte JPEG measured 320 x 240. Temporary storage used
directory mode `0700` and file mode `0600`; TTL purge left `files_remaining=0` and removed the directory.
The connection stayed authenticated and stable, returned to IDLE and emitted zero input, touch,
queue or device errors. The observer discarded 227 serial bytes, recorded
`serial_camera_frame_markers=1` and `serial_camera_error_markers=0`, and saw zero panic, watchdog, stack, heap, brownout, reset and disconnect markers. The operator reported that the
shutter sound was not heard and no screen change was seen. No image was displayed, viewed, externally processed or retained.
Postflight found a free serial device, USB attached, no listener on 8765/8766, no
capture media/directory, and the scoped firewall rule retained. HW-12 physical capture/upload and
CAM-001 were Green; at that checkpoint live Hermes `input_image` remained CAM-002 work and was
completed by the later accepted vision turn.
The HW-12 acceptance evidence host gate was Green with 379 tests passed in 31.94 seconds at 85.20%
branch coverage; formatting, Ruff, strict mypy, protocol validation, secret scan, dependency audit
and offline doctor also passed.
The successful HW-13 wrong-token recovery followed a nine-test temporary-harness Red→Green slice
with Ruff, format and strict mypy Green. The accepted repeat established authenticated IDLE, entered
exactly one wrong-token phase with `wrong_auth_failures=5.0` and
`wrong_phase_registered=false`, then restored the correct Bridge and reached
`recovery_elapsed_ms=26890`, `final_state_idle=true` and `status_commands=2`. There was no camera, audio or actuator command.
The observer discarded 1,066 serial bytes with zero boot, panic, watchdog, stack, heap, brownout and reset markers;
there were zero input, touch, queue and device-error events. The first attended run supplied the
explicit `Connecting Bridge` observation but the operator missed its recovery toast. A separately
approved repeat supplied `Bridge connected`; the operator confirmed no contact with the device,
desk or cable. No token or raw serial was displayed or retained in host evidence. Postflight found
one free serial device, USB attached, no listener on 8765/8766, no harness process, and the scoped firewall rule retained
for final Goal cleanup. This wrong-token slice is Green; the later Hermes-stop slice is recorded below.
The HW-13 evidence host gate was Green with 380 tests passed in 32.06 seconds at 85.26% branch coverage;
formatting, Ruff, strict mypy, protocol validation, secret scanning, dependency audit and offline
doctor were Green.
The successful HW-13 Hermes-stop recovery used local Mock Hermes through the production public HTTP/SSE client
with the production Gateway, voice-turn service, failure notifier and audio streamer. One bounded
stop after a ready authenticated baseline produced `failure_error_code=HERMES_FAILED`,
`failure_notification_successes=1`, `failure_audio_frames=0.0` and
`failure_turn_released=true`, then returned the device to IDLE without failure audio.
The first approved diagnostic showed a blank Japanese toast because the Firmware toast uses
`lv_font_montserrat_20`; its completed but inaudible 440 Hz recovery was also rejected as operator
evidence. Failing tests drove the ASCII failure notification and 880 Hz correction before a
separately approved repeat with no automatic retry. The operator then read `HERMES OFFLINE`, and
recovery recorded `recovery_probe_ready=true`, `recovery_turn_completed=true`,
`recovery_output_streams=1`, `recovery_audio_frames=20.0`, `recovery_elapsed_ms=35` and
`recovery_device_idle=true`. The operator heard one 880 Hz recovery tone, saw no other screen change
and confirmed no physical contact. There was no camera, microphone or actuator command and only one bounded recovery audio stream.
The observer discarded 1,412 serial bytes with zero input, touch, queue and device-error events and
zero boot, panic, watchdog, stack, heap, brownout and reset markers. Postflight left no listener or
harness; Windows reported USB attached and the scoped firewall rule retained, while WSL serial enumeration was absent.
This local Mock Hermes result covers the production public HTTP/SSE client but not a live provider;
live HW-09 remains NOT RUN. At that Hermes-stop checkpoint, HW-13 was PARTIAL pending TTS-stop,
temporary Wi-Fi-loss and camera-failure evidence.
The HW-13 Hermes-stop evidence host gate was Green with 389 tests passed in 31.83 seconds at
85.26% branch coverage; formatting, Ruff, strict mypy, protocol validation, secret scanning,
dependency audit and offline doctor were Green.
The successful HW-13 TTS-stop recovery used a 13-test temporary harness with Ruff, format and strict
mypy Green. Local Mock Hermes remained available, while a local HTTP WAV provider was used through
the production TTS adapter `GenericHttpWavTtsAdapter`, Gateway, voice-turn, notifier and streamer.
After `tts_baseline_ready=true`, the attended run used one TTS stop phase and no automatic retry.
It produced `failure_error_code=TTS_FAILED`, `failure_notification_successes=1`,
`failure_audio_frames=0.0` and `failure_turn_released=true`, while the device stayed connected and
returned to IDLE. The operator read `TTS OFFLINE`, reported no abnormal screen change and confirmed no physical contact.
A fresh provider then yielded `tts_stop_phases=1`, `recovery_tts_ready=true`,
`recovery_turn_completed=true`, `recovery_output_streams=1`, `recovery_audio_frames=20.0`,
`recovery_elapsed_ms=35` and `recovery_device_idle=true`. The operator heard one 880 Hz recovery tone.
There was no camera, physical microphone or actuator command and only one bounded recovery audio stream.
The observer discarded 23,728 serial bytes with zero input, touch, queue and device-error events and
zero boot, panic, watchdog, stack, heap, brownout and reset markers. Postflight found one free serial device,
USB attached, no listener on 8765/8766/18767/18768, no harness and the scoped firewall rule retained.
This local production-adapter result did not establish live provider status. At that TTS-stop
checkpoint, live HW-10 was NOT RUN and HW-13 was PARTIAL pending temporary Wi-Fi-loss and
camera-failure evidence.
The HW-13 TTS-stop evidence host gate was Green with 390 tests passed in 33.34 seconds at
85.26% branch coverage; formatting, Ruff, strict mypy, protocol validation, secret scanning,
dependency audit and offline doctor were Green.
The successful HW-13 camera-failure recovery used a 21-test temporary harness with pytest, Ruff,
format and strict mypy Green. Fresh explicit privacy approval covered exactly one camera command
and no host-side retry through the production `CaptureCoordinator`, `CaptureStore`, Device Gateway
and Control API. Only the upload route was deliberately configured with `capture_store=None`; a
contract test proved that it rejected authenticated media before request form/body parsing. The
physical command reached `serial_camera_frame_markers=1`, and three bounded Firmware upload
attempts all returned unavailable with `capture_store_unavailable_responses=3`.
Firmware produced `capture_completed_events=1`, `capture_completed_ok=0` and
`failure_event_forwarded=true`; Control returned `control_status=409` and
`control_error_code=CAPTURE_FAILED` after `elapsed_ms=505`. The owned lifecycle recorded
`reservations=1`, `reservation_cancels=1`, `capture_total=0.0`, `files_remaining=0` and
`temporary_directory_removed=true`. The stable authenticated connection completed
`status_commands=2` with `final_state_idle=true`, no audio or actuator command, and zero input,
touch, queue and device-error events. The observer discarded 2,924 serial bytes with zero
camera-error, boot, panic, watchdog, stack, heap, brownout and reset markers.
The host never inspected the media, and no raw image bytes, exact image hash or capture ID were displayed or retained;
the image was not viewed, displayed, externally processed or stored. The operator reported no
shutter sound and no physical contact, but screen presentation was not observed, so there is no
physical display claim. Postflight found one free serial device, USB attached, no listener on
8765/8766/18767/18768, no harness and the scoped firewall rule retained. The camera-failure path is
machine Green. At that camera-failure checkpoint, HW-13 was PARTIAL solely because temporary
Wi-Fi loss was NOT RUN.
The HW-13 camera-failure evidence host gate was Green with 391 tests passed in 34.60 seconds at
85.26% branch coverage; formatting, Ruff, strict mypy, protocol validation, secret scanning,
dependency audit and offline doctor were Green.
The successful HW-13 Wi-Fi-loss recovery used a 19-test temporary harness with pytest, Ruff,
format and strict mypy Green. Source commit `3f3ee40` produced a 3,921,040-byte diagnostic image,
SHA-256 `137d140de9f4279c86654949307003dfb6d216648e923cc84130057cd1acf4f3`, retaining the physical
motion lock. It was written only at `0x20000`; its esptool write hash, independent read-only digest
and clean 30-second boot passed. From authenticated Wi-Fi-connected IDLE, the run recorded
`wifi_cycle_commands=1`, `cycle_duration_seconds=15`, `cycle_start_acks=1`,
`cycle_restart_acks=1`, `websocket_disconnects=1.0`, `recovery_connection_replaced=true`,
`recovery_elapsed_ms=11329`, `recovery_idle=true` and `recovery_wifi_connected=true`.
There was no camera, audio or actuator command. The content-suppressed observer discarded 1,286
serial bytes with zero input, touch, queue and device-error events and zero boot, panic, watchdog,
stack, heap, brownout and reset markers. The operator saw `Connecting Bridge` and
`Bridge connected`, reported no abnormal movement or sound and confirmed no physical contact.
The 3,920,800-byte normal image from source commit `3f3ee40`, SHA-256
`32988d0d66eea2a44e690c1b593182b411f1b1408c23eeb2d0aa59a59aca7e71`, was then written only at
`0x20000`; its esptool write hash, independent read-only digest and clean 30-second boot passed,
leaving the diagnostic feature disabled. Bootloader, partition table, NVS, Wi-Fi credentials and
assets were not rewritten. The successful HW-13 Wi-Fi-loss recovery completes HW-13 as PASS.
The HW-13 Wi-Fi-loss evidence host gate was Green with 429 tests passed in 33.69 seconds at
85.32% branch coverage; formatting, Ruff, strict mypy, protocol validation, secret scanning,
dependency audit and offline doctor were Green.

## Phase status

| Phase | Result | Evidence and remaining boundary |
| --- | --- | --- |
| 0 — Investigation | Hardware baseline and live providers complete | Git, tools, licenses and pins recorded; one device, factory boot/security/partition state and backup verified; loopback-only live Hermes v0.20.0 and local faster-whisper are exercised |
| 1 — Repository scaffold | Complete | locked Python project, CI, schemas, config, docs and gates |
| 2 — Protocol and Simulator | Complete | strict schemas/models, real WebSocket handshake/command, Mock Hermes and generated media |
| 3 — Bridge Device Gateway | Complete | auth, registry, commands, audio/capture routing, Control API, health and metrics |
| 4 — Firmware control slice | Host/build/HW-01/HW-02/HW-03 complete | interactive USB/NVS, Wi-Fi, authenticated hello/status and operator-confirmed display Green; no-touch false activation reproduced and corrected; both no-touch and deliberate-touch observations Green |
| 5 — Fixed TTS | Host/Firmware build, HW-06 output and HW-11 cancellation complete | ordered Opus output, cancellation, configurable preroll/gain, reconstructed WAV tests, intelligible fixed-Japanese playback and physical cancel-before-new-turn |
| 6 — Microphone and STT | Host/Firmware build, HW-07 physical microphone and HW-08 live local STT complete | touch-to-talk Opus input, private WAV reconstruction, RMS/noise analysis, VAD silence end and maximum-duration stop physically Green; `small`/CPU/INT8 faster-whisper recognized three ephemeral Japanese patterns and returned empty for silence |
| 7 — Hermes Responses API | Host/Mock/live complete | public health/capabilities/Responses/SSE, conversation/session and typed error behavior; v0.20 nested capabilities plus three required live turns Green |
| 8 — Streaming voice loop | Host/Simulator and HW-11 physical cancellation complete | segmentation, concurrent synthesis/ordered playback, cancellation, full mock round trip and clean physical new-turn playback after cancel |
| 9 — MCP | Host complete; live Skill path Green | separate stdio server, ten bounded tools and loopback Control client; live `skill_view` use observed while live MCP ingestion remains unexercised |
| 10 — Camera and vision | Complete, including CAM-002 live physical vision | finite authenticated JPEG upload, physical capture/store/fetch/TTL lifecycle, live Hermes `input_image`, spoken response and immediate deletion are Green |
| 11 — Hardening | Host/Firmware/reconnect/HW-13 complete | faults, reconnect, races, limits, security, privacy, metrics, doctor and debug report; wrong-token, local-public-contract Hermes-stop/TTS-stop, camera-failure and attended device-local Wi-Fi-loss recovery are Green |
| 12 — Packaging and docs | Complete, including final cleanup | services, safe scripts, enabled build gate, operations, requirements, traceability and cleaned temporary connectivity |

## Implementation and evidence history

The entries below are chronological and intentionally retain intermediate fail-closed or PARTIAL
results. The current status is the summary above and the final checkpoint near the end of this file.

- Protocol v1 has bounded JSON/raw-Opus contracts, strict Pydantic dispatch and valid/invalid
  examples.
- Bridge exposes only the LAN Device Gateway/capture surface and loopback Control/metrics surface;
  Hermes integration uses documented public OpenAI-compatible endpoints only.
- Commit `c94efb5` adds a label-free `touch_events_total` counter on the shared runtime registry,
  allowing the next one-device observation to distinguish touch delivery from microphone frames
  and active-turn behavior without retaining coordinates or content. The corrected physical head-
  sensor path is verified through its direct audio-input lifecycle, but that Firmware path does not
  emit `touch.*`; a physical `touch_events_total` increase therefore remains unverified.
- Voice, vision, command, capture, cancellation, tool-progress and reconnect paths run against the
  Device Simulator and Mock providers without tracked audio or image fixtures.
- Tokens, media, logs and reports have explicit lifetime, permissions, redaction, rate and size
  controls. Debug audio is disabled by default.
- Backup, hardware-smoke, service and debug-report tooling defaults to non-destructive behavior.
  The attended visual-smoke mode added in `a95319e` requires a K151 with `head=false`, accepts an
  explicit brightness restore value, sends no head command and independently attempts every
  visual restore. In the repeated attended physical run, both application/restoration sequences
  exited 0 with stable metrics, and the operator saw brightness 35 and the dim-blue LEDs. Happy
  remained absent because the flashed launcher acknowledged expression without initializing an
  avatar. A failing contract test preceded the `421457b` correction; its Firmware build is Green,
  and the retained correction was later flashed only at `0x20000`, independently verified and
  physically confirmed. An expression-only 20-second run kept one K151 connected with
  `head=false`; the operator saw the happy eyes, idle restoration was acknowledged, and no
  disconnect, authentication failure, timeout, touch, audio input or active turn occurred.
- Commit `4d129c7` adds a loopback GET-only HW-05 observer that requires the target device ID,
  K151 identity and `head=false`, rejects a one-poll transient, and measures confirmed Control/API
  outage to re-registration. The first valid baseline measured 4052.5 ms including its deliberate
  3.0-second Bridge-down hold, but no reconnect display was visible.
- The first Red→Green correction in `e73dc30` routed both reconnect states to global notifications.
  Its approved 3,918,512-byte app was flash/digest verified, yet a second controlled run recovered
  in 9461.9 ms with neither toast visible. A manual 30-second global toast was independently seen,
  isolating the state path behind launcher-false `IsSetupUICalled()`.
- A new failing contract test preceded `7913742`, which separates notification presentation from
  avatar initialization. Its approved 3,918,528-byte motion-locked app was written only at
  `0x20000` and independently verified. The final observer confirmed loss twice and measured
  15,697.6 ms including a deliberate 3.0-second hold; the same K151 with `head=false` returned,
  simultaneous serial observation saw no reset/panic/watchdog marker, and the operator saw both
  `Connecting Bridge` and `Bridge connected`. `Connecting Bridge` appeared lower in the toast
  stack, retained as a UX follow-up.
- The physical shutdown also exposed one already-handled turn failure whose background task
  exception had not been retrieved. A failing unit test reproduced the warning before `eef1390`
  added result retrieval; the relevant 13 audio/voice/runtime tests are Green. No debug media was
  enabled or retained and no live provider was invoked.
- The final expression-session Ctrl+C stopped and cleaned up correctly but printed a peer-lifespan
  cancellation trace because Uvicorn re-raised the captured SIGINT before both servers had
  finished. A failing unit test preceded `85e2c2a`; an actual two-loopback-server check now exits
  130 without a traceback while still coordinating both shutdown flags.
- Early fixed-speech trials used a BOM-less UTF-8 PowerShell script that Windows PowerShell 5.1
  decoded as ANSI, so literal Japanese became mojibake before synthesis. A two-beep control was
  physically heard twice and isolated the decoder/resampler/I2S/internal-speaker path as Green. The
  corrected source used explicit Unicode code points; its final processed candidate was recognized
  as `こんにちは` with confidence `0.9625`, encoded into 30 Opus frames and hash-locked as
  `ffb45d626fcbf1c15058dd839658fd27535b64d8a9dea5ce226e526975346148` before transmission. On the
  K151, all frames completed with clean counters, state returned to IDLE, volume restored `85 → 70`,
  and the operator reported the phrase properly audible. HW-06 PASS; no product-code fix was needed.
- The subsequent volume comparison reused one identical deterministic 25-frame beep stream at
  volume 45 then 85. Both plays were audible, returned IDLE and restored 70 with zero transport,
  codec or device errors. The operator later confirmed that the second volume-85 play was clearly
  louder than the first volume-45 play, making comparative volume Green. Its observer nevertheless
  received one `audio.input.start` and one
  `audio.input.end` while the operator touched nothing. No incoming content was saved, printed,
  transcribed or analyzed. That unsolicited lifecycle remains a safety finding, not acceptance; it
  was later superseded for HW-02 by a controlled corrected-touch observation.
- HW-11 used only bounded in-memory Mock-TTS tones through the production Gateway/output path.
  The accepted trial sent a first 30-frame 880 Hz stream, issued cancel after the configured delay,
  observed IDLE, then sent a second distinct 20-frame 880 Hz stream after 1250 ms. The new turn
  entered `SPEAKING`, completed and returned IDLE with zero underrun, overflow, device-error and
  input events. The operator's short-then-long beep report and no-contact confirmation make the
  physical cancellation/new-turn Green. The preceding inaudible 440 Hz/no-contact-input finding
  and one transient queue-error run remain explicitly rejected diagnostic evidence. The former is
  retained as a historical intermittent no-contact input-safety finding; its mechanism has not been
  inferred.
- A separately attended bounded silent/440/880 comparison then ran six 1.2-second, 20-frame phases
  through the production Gateway. Each entered `SPEAKING`, completed and returned IDLE on the same
  authenticated connection; input starts, frames and ends all remained zero, along with touch,
  queue and device-error counters.
  The operator heard two separated 880 Hz tones and confirmed touching neither the device, desk nor cable.
  The historical intermittent no-contact input-safety
  finding was not reproduced in this bounded comparison; the input-safety follow-up is Green, with
  no retained content and no inferred cause or permanent correction.
- A failing startup-noise test preceded the minimal idle qualification. A second Red reported
  `stable touch did not emit a press` before `HeadTouchDebouncer` gained three-sample press/release
  confirmation. Held-startup and transient operational noise cases are also Green. The integrated
  HAL in `e19098d` now uses the configured intensity threshold and debouncer before emitting
  gestures.
- Firmware protocol/state/reconnect/settings/commands/audio/camera/touch code is isolated and
  covered by 19 host C++ tests. A fresh Bridge-enabled, primary-USB, motion-locked ESP-IDF image
  builds successfully at 3,918,672 bytes (24% free), SHA-256
  `f35c24a94d20860d0a709973828035920997e38b1ed934a6d1fbbf3bcc54e43d`; this temporary image is
  build evidence only. The separately retained candidate is now physically flashed and
  digest-verified, and its attended no-touch behavioral regression is Green.
- K151 conservative motion profile: yaw `-45..45` degrees, pitch `5..85` degrees, speed `1..30`
  (default `15`), home `0/45` degrees. Failing tests preceded matching Bridge, MCP and Firmware
  reject-not-clamp enforcement, a midpoint home, the narrowed HAL angle envelope and disabled
  continuous yaw PWM. The source basis is recorded in `firmware/UPSTREAM.md`. The normal release
  build still advertises `head=false` and keeps the servo-output lock enabled. The current physical
  device instead contains the attended candidate described below; its authenticated `head=true`
  capability and one initial bounded command have now been physically checked.
- Commit `8384214` adds `CONFIG_STACKCHAN_HERMES_LOCAL_MOTION_LOCK=y` as a second, default-on lock
  for an attended globally unlocked candidate.
  Local, avatar, IMU, BLE and app motion plus local torque enable are rejected; only an authenticated
  Bridge command that already passed the K151 profile can seed movement. Its retained app is
  3,921,232 bytes, SHA-256
  `af98e32ce32aa21214d4c8e29440fb2785b1f2f020f405ae2e049a332ebd7d7d`, with valid image hashes,
  24% headroom, factory-identical partition table and one `0x20000` app argument. It is now flashed
  and digest/boot verified. Its flash approval did not authorize a later physical motion command.
- The 2026-09-03 attended motion-candidate preflight passed against exactly one free stable serial
  identity. The 16 MiB private backup, SHA sidecars and permissions recomputed correctly; its
  partition matched the candidate byte-for-byte. Secure Boot and Flash Encryption stayed disabled,
  and the current motion-locked app matched its retained digest before esptool issued its final hard
  reset for normal boot. The exact scoped firewall rule remained present with no 8765/8766 listener. There
  was no flash write or physical head command; explicit flash approval remains pending.
- The 2026-09-03 attended motion-candidate app-only flash followed a distinct explicit approval.
  Exactly the 3,921,232-byte app was written at `0x20000`; esptool's write hash and an independent
  post-write digest both matched. A 35.09-second content-suppressed boot window discarded 11,874
  serial bytes and observed one boot marker, one Firmware-version marker and two reset markers,
  with zero panic, watchdog, stack, heap, brownout, camera-error, disconnect or reopen markers.
  Postflight retained one free stable serial, no Windows/WSL listener and the one scoped firewall
  rule. The authenticated motion capability still requires a pre-command check; no physical head
  command has been sent, and physical motion approval remains pending as a distinct approval.
- The 2026-09-03 attended initial K151 motion used a fresh distinct approval after commit `c033aff`
  made the physical smoke helper fail closed on an HTTP-success/device-`ok=false` result. Preflight
  reverified one stable serial, the factory backup, candidate digest, exact Hyper-V firewall rule,
  default inbound Block and zero listeners. A process-only token authenticated the exact K151 on
  Firmware `1.5.1` with `head=true` and initial IDLE. Exactly one `head.set_angles` command used
  `yaw=5`, `pitch=45`, `speed=10`, with no retry or follow-up/home command. Machine evidence recorded
  `motion_commands=1`, acknowledged success, stable connection, final IDLE, 143 discarded serial
  bytes and zero device/servo, queue, input, touch, boot, reset, panic, watchdog, stack, heap,
  brownout, camera-error, disconnect or reopen markers. The operator observed motion, reported no
  abnormal sound, vibration or heat, and touched neither the device, desk nor cable. Postflight
  again had one free stable serial and no listener or harness. The physical yaw/pitch/home sequence
  remains incomplete; the observed movement alone is not interpreted as direction-specific proof.
- The 2026-09-03 attended K151 home attempt used a separate approval and a home-only harness built
  Red→Green with 15/15 tests plus format, Ruff and strict mypy checks. Preflight again verified one
  stable serial, factory backup, candidate digest, exact scoped firewall/default inbound Block and
  zero listeners. It sent exactly one `head.home` command and no retry or additional motion command.
  The device acknowledged it with `motion_commands=1`, `home_commands=1`, `angle_commands=0`, stable
  connection and final IDLE. Fault, touch, boot, reset, panic, watchdog, stack, heap, brownout,
  camera-error, disconnect and reopen counts were zero. However, the same 4,450 ms observation
  contained `input_starts=1`, `input_frames=41`, `input_ends=1` despite the operator touching neither
  the device, desk nor cable, so the fail-closed result was `machine_valid=false`. The operator did
  not observe movement because the head appeared already centered, and reported no abnormal sound,
  vibration or heat. No cause is inferred for the unsolicited input lifecycle; physical home
  remains unestablished. Postflight again found one free serial and no listener or harness, while
  the scoped firewall rule remains for final Goal cleanup.
- The 2026-09-03 attended K151 positive-yaw observation used another distinct approval. The yaw-only
  harness was built Red→Green with 20/20 tests plus format, Ruff and strict mypy checks; the existing
  smoke helper was 8/8 Green. Preflight reverified the unique serial, backup, candidate digest,
  exact scoped firewall/default inbound Block, zero listeners, exact K151/Firmware `1.5.1`/`head=true`
  identity, IDLE and zero audio/event/serial activity. It then sent exactly one `head.set_angles`
  command with `yaw=10`, `pitch=45`, `speed=10`, and no retry or home command. Machine evidence was
  `machine_valid=true` with `motion_commands=1`, `angle_commands=1`, `home_commands=0`,
  `exact_yaw_commands=1`, acknowledged success, stable connection, final IDLE, 337 discarded serial
  bytes and `input_starts=0`, `input_frames=0`, `input_ends=0`; all fault, touch, reset and reconnect
  counters were also zero. The operator observed the face move slightly to the left when viewed from
  the front, reported no abnormal sound, vibration or heat, and touched neither the device, desk nor
  cable. Postflight retained one free serial and zero listeners/harnesses. The positive yaw direction
  is physically established; pitch and home remain unestablished, and the firewall remains for final
  Goal cleanup.
- The 2026-09-03 attended K151 return-home observation reused the separately approved single
  return-home action while the head remained at the verified positive-yaw offset. The temporary
  harness evolved Red→Green to 52/52 tests plus format, Ruff and strict mypy checks, including a
  ±2-degree servo-readback tolerance after an exact-float preflight safely rejected the quantized
  position. Every preceding start stopped before a motion command. The final armed run released one
  `head.home`; the operator observed a rightward return to center, confirmed the centered result,
  reported no abnormality and touched neither the device, desk nor cable. Result collection then
  ended as `unexpected_error` with `machine_valid=false`, so no complete machine evidence is
  inferred. A separate stdin-closed read-only follow-up returned `position_home=true` and
  `position_offset=false` without sending motion. Thus physical return-to-home motion was observed,
  but machine-valid home completion remains unestablished. Postflight found one serial, zero
  Windows/WSL listeners and no harness, while the one scoped Hyper-V rule remains for final Goal
  cleanup.
- The 2026-09-03 attended K151 pitch observation used a new distinct approval from the independently
  confirmed home position. The pitch-only harness was developed Red→Green to 61/61 tests, with
  format, Ruff and strict mypy Green; the existing smoke helper was 8/8 Green. Preflight passed one
  serial, zero listeners/harnesses, exact scoped firewall/default-Block, backup, candidate digest,
  device identity, `head=true`, IDLE, home-position and quiet audio/event/serial gates. It sent
  exactly one `head.set_angles` at `yaw=0`, `pitch=40`, `speed=10`, with no retry or home command.
  Machine evidence was `machine_valid=true`, `motion_commands=1`, `angle_commands=1`,
  `home_commands=0`, `exact_pitch_commands=1`, acknowledged success, stable connection, final IDLE,
  `initial_pitch=45.3`, `final_pitch=40.3`, 143 discarded serial bytes and zero
  input/touch/fault/reset/reconnect/backtrace evidence. The operator observed the head move downward
  when viewed from the front, reported no abnormal sound, vibration or heat, and touched neither the
  device, desk nor cable. Postflight retained one serial, zero Windows/WSL listeners/harnesses and
  the one scoped rule. The decreasing pitch direction is physically established; machine-valid home
  completion remains unestablished, so HW-04 remains PARTIAL.
- The 2026-09-03 attended K151 machine-valid home used a new distinct approval from the verified
  `pitch=40` position. The home-only harness was developed Red→Green to 57/57 tests, with format,
  Ruff and strict mypy Green; the existing smoke helper was 8/8 Green. Preflight reverified one
  serial, backup, candidate digest, exact K151/Firmware `1.5.1`/`head=true` identity, IDLE, bounded
  `yaw=0`/`pitch=40` readback and quiet audio/event/serial gates. It released exactly one
  `head.home` command with no retry or additional motion command. Machine evidence was
  `machine_valid=true`, `motion_commands=1`, `home_commands=1`, `angle_commands=0`,
  `exact_home_commands=1`, acknowledged success, stable connection, final IDLE and three bounded
  position reads: `initial_pitch=40.3`, `final_pitch=44.3`, with final yaw 0.6 degrees. The 4,497 ms
  window discarded 277 serial bytes and had zero input/touch/fault/reset/reconnect/backtrace
  evidence. The operator observed one upward movement, reported no abnormal sound, vibration or
  heat, and touched neither the device, desk nor cable. The operator could not resolve the fine
  final angle by eye and did not see a second movement; one movement is the expected home action,
  while the bounded readback establishes the final position. Postflight found one serial, zero
  Windows/WSL listeners and harnesses, a clean worktree before evidence edits, the one exact scoped
  Hyper-V rule and default inbound Block. Machine-valid home completion is established. Together
  with the prior yaw, pitch, expression, LED, brightness and volume evidence, HW-04 is PASS.

## Remaining stop conditions

- HW-01 is **PASS**: exactly one device and a complete 16 MiB factory image were verified by
  per-region device digests, stored SHA-256 and a final whole-device digest comparison. Private
  identifiers and backup artifacts remain ignored local evidence.
- The approved custom-Firmware flash and corrected application reflashes are complete. HW-02 is
  **PASS**: stable boot, primary USB REPL input, all five provisioning writes and physical
  Wi-Fi/IP acquisition, authenticated hello and display-command acknowledgement are Green without
  panic or watchdog evidence. The operator independently saw `HERMES OK 0831` on the LCD while
  disconnect and command-timeout metrics stayed zero. The corrected no-touch path is Green, and a
  single deliberate touch/release produced exactly one bounded touch-to-silence input lifecycle.
- The explicitly approved, named WSL-only TCP 8765 `LocalSubnet` firewall rule served the continuous
  hardware campaign without changing Windows default inbound policy. Final Goal cleanup is
  complete: the exact rule, USB attachment, Bridge/TTS helper connectivity and authenticated
  Hermes tunnel were removed after the final evidence/gates.
- HW-01 through HW-13 are **PASS**. HW-11 PASS combines clean machine
  evidence with the independent short-then-long physical observation. For HW-04, brightness, LED,
  expression and comparative volume were physically Green before the bounded motion sequence.
  Earlier home attempts remain historical inconclusive/fail-closed evidence. Exact `yaw=10` and
  `pitch=40` commands subsequently established positive yaw and decreasing pitch. The final
  separately approved `head.home` ran once from measured pitch 40.3 to 44.3 degrees with complete
  clean machine evidence; the operator observed its single upward movement, no abnormality and no
  contact but did not independently judge the fine final angle by eye. The bounded final readback
  establishes home, so machine-valid home completion is established and HW-04 is **PASS**.
  HW-08 live local faster-whisper STT, HW-09 live Hermes Responses API and HW-10 live physical
  full voice are **PASS**.
- HW-12 is **PASS**. The failing shutter-audio boundary contract and minimal correction landed in
  `8ad0489`; its retained app is flash/digest/boot verified. The successful post-correction HW-12
  capture completed one newly consented authenticated capture/upload/store/fetch/TTL lifecycle and
  purged all temporary media. CAM-002 later completed the live Hermes `input_image` boundary.
- HW-13 is **PASS**. In addition to the earlier wrong-token, Hermes-stop, TTS-stop and camera-failure
  recovery evidence, one device-local 15-second Wi-Fi loss produced one authenticated disconnect,
  a replacement connection after 11,329 ms and Wi-Fi-connected IDLE recovery. Both reconnect
  messages were visible with no abnormal movement, sound or contact. The one-shot diagnostic was
  then removed by restoring the independently verified motion-locked normal release.
- The isolated inaudible 440 Hz probe's no-contact input lifecycle remains historical intermittent
  evidence. Its prescribed bounded silent/440/880 comparison is complete and Green: six valid
  machine phases had zero input/touch/error evidence and the operator confirmed the expected two
  sounds with zero contact. It was not reproduced in this bounded comparison; no content was
  retained and no cause or permanent correction is inferred.
- CAM-002 live physical vision is **PASS**. Its fresh explicit privacy consent covered one capture
  with no automatic retry; the answer matched the scene and the owned image was deleted. The
  follow-up sustained-touch regression is also physically Green. No further external-evidence
  scenario remains in the Goal.
- Remote head capability was enabled only on the completed attended motion candidate while its
  local source lock rejected avatar/IMU/BLE/app motion and local torque enable. The current device
  is back on the normal release with the global head-motion lock enabled.
- The loopback-only live Hermes public API/key is available through the active SSH tunnel and its
  text/Skill capability and latency are measured. Local faster-whisper STT quality and latency are
  measured. HW-10 measured 12.134 seconds to first audio and 20.881 seconds end to end with an
  intelligible physical answer. The live image answer is also physically accepted.

## Latest verification evidence

- `./scripts/run-simulator-e2e.sh`: exit 0; 9 passed in 1.90 seconds.
- Current pre-flash full Firmware-bearing `./scripts/verify.sh` with ESP-IDF v5.5.4 active: exit 0;
  **438 tests passed** with **85.45%** coverage, followed by 22/22 Firmware CTests, six locked Git
  repositories, 60 managed components and a fresh **3,920,848-byte** ESP-IDF build. Formatting,
  lint, strict mypy, protocol validation, secret scan, dependency audit and offline doctor were
  Green. The retained final image from source commit `d88f6df` is
  `firmware/build-hermes-touch-filter-d88f6df/stack-chan.bin`; it has SHA-256
  `32ec714f11a7c906e6ff73f3c7813f3ed5a0fb06328df1b6db0acba1ae54d881` and remains
  motion-locked. Its app-only flash, independent digest and clean boot discarded 13,251 serial
  bytes without fault evidence.
- The main-task shutter-audio correction checkpoint remains recorded as 377 tests passed in 30.88
  seconds at 85.26% branch coverage, 20/20 Firmware CTests and a fresh 3,919,968-byte build.
- Firmware host tests: 22/22; six Git repositories and 60 managed components verified.
- Previous flashed HW-12 acceptance candidate from source commit `8ad0489`:
  `firmware/build-hermes-hw12-shutter-8ad0489/stack-chan.bin`, 3,919,968 bytes; SHA-256
  `8b55b48a84e71820456dee68d16a2e73a7eb5ab836a8a3e8bd0638fe4686e296`. Its app-only write,
  independent digest and three consecutive clean boot windows passed after one unexplained
  transient stack overflow did not reproduce. The successful post-correction HW-12 capture sent
  exactly one newly consented camera command with no automatic retry, completed authenticated
  upload/store/fetch/TTL cleanup, returned to IDLE and retained no media. HW-12 is PASS.
- The later HW-13 camera-failure recovery sent one separately consented command with no host-side
  retry. Three bounded upload attempts were deliberately rejected before body parsing; the failed
  completion reached Control as `CAPTURE_FAILED` in 505 ms, returned to IDLE and retained no media.
  Machine and serial evidence were clean. The operator heard no shutter sound and confirmed no
  physical contact; screen presentation was not observed. That path is machine Green.
- Previous flashed HW-10 release from source commit `f73ff28`:
  `firmware/build-hermes-hw10-final-f73ff28/stack-chan.bin`, 3,920,864 bytes; SHA-256
  `41cd8affc309006f7fc1adaaeafe5f50cf1b1bc2e4daf1322cff6b29cac6489c`. It retains the physical
  head-motion lock (`CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y`), disables the attended Wi-Fi
  diagnostic and includes the `9f42b92` touch re-arm.
  Its app-only write, independent read-only digest and clean 35-second boot passed.
- Retained HW-11 correction candidate from source commit `e824ef4`:
  `firmware/build-hermes-hw11-e824ef4/stack-chan.bin`, 3,919,184 bytes; SHA-256
  `6167fec5380d78fbc6026d6a931169e1f39d0dd5eef12a9897a84f393860cfec`; valid checksum and
  validation hash; app partition 24% free. Its one-device/backup/security/config/partition preflight,
  approved app-only write, independent digest, 12,494-byte clean boot observation and attended
  HW-11 cancel/new-turn evidence are Green.
- Latest isolated no-touch-safety Firmware gate: 19/19 host tests; six Git repositories and 60
  managed components verified; fresh image 3,918,672 bytes, 24% free, SHA-256
  `f35c24a94d20860d0a709973828035920997e38b1ed934a6d1fbbf3bcc54e43d`; not flashed.
- Latest combined-gate temporary image with the no-touch correction: 3,918,672 bytes; SHA-256
  `391d06617aab21bc2e1106faec8ce5d872bcc4bc3217e80dcea1699cbd4bf39a`; app partition 24% free;
  not flashed.
- Retained no-touch correction candidate from source HEAD `fffaba3`:
  `firmware/build-hermes-head-touch-fffaba3/stack-chan.bin`, 3,918,672 bytes; SHA-256
  `cf122cd787fae325e38ba3caa2b743e2c4386559d2e46f94e93333d69f8e4551`; valid internal checksum
  and validation hash; app partition 24% free. Its private generated configuration retains Bridge,
  USB provisioning, primary USB console and physical motion lock. The partition table matches the
  predecessor and its sole app entry is `0x20000 stack-chan.bin`.
- Its attended read-only preflight then reconfirmed one stable serial identity, the complete
  digest-verified 16 MiB factory backup, unchanged security state, the factory partition table and
  all required candidate settings. The current expression app still matched its retained digest.
  At that preflight checkpoint no write command had been executed.
- After explicit approval, only the retained 3,918,672-byte app was written at `0x20000` in 19.9
  seconds. Esptool's write hash and an independent `verify_flash` digest comparison both passed.
  A content-suppressed 30-second boot observation collected 12,679 bytes with one Firmware `1.5.1`
  marker, two reset markers and zero panic/abort/watchdog markers. The app is physically flashed and
  digest-verified. Its later attended 60.03-second no-touch regression and 51.11-second deliberate-
  touch observation are physically Green.
- Retained primary-USB/motion-locked display candidate:
  `firmware/build-hermes-toast-init-6faa72e/stack-chan.bin`, 3,918,448 bytes; SHA-256
  `ed581f4ad8374325729558233da2dbde329f58d5732e0254f3b2b5ad7e26dc79`; 24% free; application
  partition flash verification and physical display confirmation matched.
- Superseded first reconnect-display app, physically flashed and digest-verified before its
  launcher-state defect was isolated:
  `firmware/build-hermes-reconnect-toast-e73dc30/stack-chan.bin`, 3,918,512 bytes; SHA-256
  `7828fa05e4dc8bdd840694050a5c1c24f3df43e3d468c43f0a52e26d4a223050`; app partition 24% free.
- Previous flashed reconnect app:
  `firmware/build-hermes-reconnect-launcher-7913742/stack-chan.bin`, 3,918,528 bytes; SHA-256
  `ae5ced6a224c0991ff4d9164eec471341cb7b43404bb574762ba9aed9ba2d1a1`; app partition 24% free.
  The independent read-only device comparison matched immediately before the expression update.
- Firmware-gate Bridge-enabled/primary-USB/motion-locked temporary `stack-chan.bin` for the
  `421457b` expression correction: 3,918,576 bytes; SHA-256
  `4dd63efe2599ef42d37d40a3fa2002101bb917fe0f78ab6a24531ec27da90901`; app partition 24% free.
  It is build evidence only and has not been flashed.
- Previous expression-correction combined-gate temporary image: 3,918,576 bytes; SHA-256
  `750811cc710e486d8f4f24cae078da1089328da07e05eb595ff81e70b986c986`; app partition 24% free.
  Its embedded compile time differs from the isolated build; it was not flashed.
- Previous flashed expression app retained from committed HEAD `bd49497`:
  `firmware/build-hermes-expression-bd49497/stack-chan.bin`, 3,918,576 bytes; SHA-256
  `78d200403f9d028b690cc50f1d1f7e7d69007c517164506d7f2b09ac5b0ebb2b`; app partition 24% free.
  Image checksum/validation hash, required Hermes/USB/motion-lock settings and the one-entry
  `0x20000 stack-chan.bin` app-only argument file passed inspection. The previous `7913742` app
  matched before this candidate was written only at `0x20000`; esptool's write hash and a separate
  read-only digest both matched. A 30-second deliberate-reset window captured 13,086 bytes, one
  Firmware `1.5.1` marker and one expected ROM/reset pair with no panic, abort, LoadProhibited or
  watchdog marker. The operator then independently saw the happy eyes during a 20-second
  expression-only run, and idle restoration succeeded.
- Protocol: 11 valid and 8 expected-invalid examples; secret scan Green.
- Hardware scenarios: **HW-01 through HW-13 PASS**; physical display, touch, brightness, LED,
  expression, full voice, cancellation/new-turn and camera capture lifecycle, bounded yaw/pitch/home
  and Wi-Fi-loss recovery plus live Hermes text/Skill Green. The earlier volume comparison's unsolicited no-touch input lifecycle is a fixed and
  physically regression-tested historical safety finding. The boot, USB input, NVS key,
  null-envelope, hardware-identity, display lifecycle and reconnect-presentation defects were fixed
  by Red→Green commits `fca58cf`, `ab7f1e4`, `a6c882e`, `4abe3d9`, `0a3bad2`, `b7b2830`,
  `6faa72e`, `e73dc30`, `7913742` and `421457b`. The reconnect and expression corrections are both
  physically flash/digest/visibility verified.

Final Goal cleanup is complete. After evidence commit `a49adc8`, the final read-only audit recorded
`StackChanHermesBridge8765` rules=0 and all WSL Hyper-V `DefaultInboundAction=Block`. The reviewed
USB device is `Shared`, not `Attached`, with no WSL serial directory. There is no listener on
8765/8766/8642/50031; temporary TTS and SSH tunnel processes are absent, the SSH control socket is
absent, the temporary touch harness and Goal-owned `/tmp` artifacts are absent, and there is no
capture or audio media. The repository was clean immediately before this cleanup-evidence update.
