# Verification report

Status: host/Simulator and integrated custom Firmware automated gates are Green; physical hardware
`HW-01` through `HW-13` are PASS. HW-09 live Hermes Responses API is PASS. HW-08 live local
faster-whisper STT is PASS. HW-10 live physical full voice turn is PASS. HW-04 is PASS: brightness,
blue LEDs, corrected happy expression, comparative volume and the bounded K151 yaw/pitch/home
sequence are physically and mechanically Green. HW-06 audio output is PASS: the corrected fixed Japanese source was
machine-recognized, transmitted as Opus and properly audible on the physical K151 with clean counters,
IDLE return and volume restoration. The previously flashed motion-locked cancellation-corrected app
was digest verified and had a clean 30-second deliberate-reset observation. Separately, the controlled
reconnect returned to the same K151 without serial reset/panic/watchdog markers, and both reconnect
toasts were independently visible. HW-07 physical audio input and HW-11 physical cancellation are
PASS. HW-12 physical camera capture/upload is also PASS. CAM-002 live physical vision turn is
PASS. HW-13 is PASS with physical wrong-token rejection/recovery,
local-public-contract Hermes-stop, HTTP-WAV TTS-stop, camera-failure and attended device-local
Wi-Fi-loss recovery Green. The diagnostic image was removed from the device after the bounded run.
A later no-touch volume comparison emitted one unsolicited input start/end lifecycle despite the
operator touching nothing. No input content was retained. The startup-qualified three-sample
debounce correction is host/ESP-IDF-build Green, app-only flashed, independently digest-verified and
clean-boot observed. Its separately consented 60.03-second no-touch regression is physically Green;
a separately consented 51.11-second deliberate touch/release is also Green, completing HW-02. All
input packets in that earlier check were immediately discarded without quality or stop-path
assessment. A later consented private capture verified short-speech quality/silence ending and an
independent maximum-duration stop, completing HW-07 without replay, transcription or external
processing.
The current device contains the motion-locked `d88f6df` release with its Wi-Fi diagnostic disabled;
it combines the stable-idle touch re-arm with sustained six-sample press qualification.
For HW-09, a loopback-only Hermes Agent v0.20.0 API on a private local host was reached through
authenticated SSH forwarding. Its current nested capability document reproduced the Bridge's prior
flat-schema incompatibility before the TDD fix in `8cb295e`. Live readiness then passed every required check.
Production Responses/SSE turns for `こんにちは`, `今日の日付を教えて` and an explicit `ascii-art`
Skill request completed in 2,721 ms, 5,665 ms and 8,590 ms. The date was correct and the Skill turn
completed two `skill_view` calls with a matching Skill reference. On the Bridge side, the API key
was process-only and never printed or stored. The compatibility-code checkpoint passed 432 tests in 32.32 seconds at
85.26% coverage before the evidence contract was added.
For HW-08, the production faster-whisper adapter loaded the locked `small` model on CPU/INT8.
Ephemeral 16 kHz mono samples from the pre-existing macOS `Kyoko` voice produced exact results for
`こんにちは` and `今日の日付を教えて` in 3,689 ms and 2,150 ms, and the semantically equivalent
`スタックちゃん、元気ですか?` result in 2,238 ms. One second of all-zero PCM returned empty in
10,961 ms. Remote temporary AIFF files were removed by an EXIT trap, in-process PCM was discarded,
and no audio retained. This provider evidence was later combined with the physical path in HW-10.

For HW-10, a separately consented predecessor run produced the historical duplicate-turn and
underrun finding: 112 input frames, 121 output frames, one STT, one Hermes request, two TTS segments,
two turn outcomes and five playback underruns despite one physical contact. Failing tests preceded
the minimal fixes: `9f42b92` requires stable idle before touch re-arm, and `f73ff28` paces audio
against absolute monotonic deadlines. The resulting full `./scripts/verify.sh` gate recorded
436 tests passed at 85.45% coverage, 22/22 Firmware CTest and a fresh ESP-IDF build. Its retained
3,920,864-byte motion-locked app, SHA-256
`41cd8affc309006f7fc1adaaeafe5f50cf1b1bc2e4daf1322cff6b29cac6489c`, was flashed only at
`0x20000`, independently digest-verified and clean-boot observed.

HW-10 live physical full voice turn is PASS. The 2026-09-04 final run used one fresh microphone
consent, one head touch and `今日の日付を教えて`, with no retry or additional contact. It accepted
63 input frames, sent 129 output frames, and completed one STT, one Hermes and one completed turn
with two TTS segments. Relative to the fixed Bridge-restart baseline, it had zero connection,
disconnection, underrun, overflow, decode, auth and timeout deltas, then returned to zero active
turns. The operator heard and understood the answer and reported no `Connecting Bridge` toast,
abnormality or additional contact. No recording was retained, and no camera or head motion was used.
Time to first audio was 12.134 seconds and end-to-end turn duration was 20.881 seconds.

CAM-002 live physical vision turn is PASS. One fresh camera consent covered one capture, one live
Hermes vision request and one spoken response, with no automatic retry. Machine evidence recorded
`capture_total +1`, 100 output frames, DELETE returned 204 and `files_remaining=0`. The operator
heard and understood the answer, confirmed that the description matched the camera scene, and saw
no `Connecting Bridge` toast, unexpected display change, physical contact or abnormality. The host
did not display, print or retain the JPEG.

The same window exposed a separate one no-contact input frame before vision, with no STT request.
The previous three-sample correction is retained as historical evidence but was insufficient for
this shorter burst. Red tests preceded the `d88f6df` thresholds of six consecutive 50 ms press
samples and three consecutive release/idle samples. The pre-flash full gate recorded 438 tests
passed at 85.45% coverage and 22/22 Firmware CTest. The retained motion-locked image is
`firmware/build-hermes-touch-filter-d88f6df/stack-chan.bin`, 3,920,848 bytes, SHA-256
`32ec714f11a7c906e6ff73f3c7813f3ed5a0fb06328df1b6db0acba1ae54d881`, from source commit
`d88f6df`. Its app-only write, independent digest and clean boot passed; 13,251 serial bytes were
discarded without fault evidence.

The separately consented physical follow-up used a 60.000-second no-touch window, then one
approximately one-second deliberate touch with no speech. No-touch input counts stayed zero; the
intentional touch yielded one lifecycle with 20 Opus frames and 2,878 bytes, followed by a
10.001-second post-touch quiet window and no automatic retry. Content was immediately discarded.
The operator confirmed one touch/release, no speech, no screen change, no other contact and no
abnormality. The aggregate returned `connection_stable=false`, but setup timing was not retained;
that auxiliary value is not used as connection-stability evidence. The sensor-specific result is
Green, while HW-05 remains the independent connection-reliability evidence.

The final documentation full gate completed with 439 tests passed in 32.52 seconds at 85.45%
coverage, 22/22 Firmware CTest, locked-dependency verification and a clean ESP-IDF v5.5.4 build.
Its temporary 3,920,848-byte verification image had SHA-256
`fb4193c340c29fc9e5861b81de85a113da91bedd96969ab3d44a7550873f09ac`; it is build evidence and
was not flashed.
For HW-12, source commit `8bfc589` is app-only flashed, independently digest-verified and clean-boot
observed. One consented camera request progressed from the predecessor's `COMMAND_TIMEOUT` to
`CAPTURE_TIMEOUT`; this verifies command-result ordering but not capture/upload completion. Commit
`517011a` now propagates an owned `camera.completed(ok=false)` as `CAPTURE_FAILED`. A second
separately consented request ended after 45,227 ms at `device_reconnected_or_disconnected` with
`capture_completed_events=0` and no upload. Commit `f6f0d2d` gives the camera worker a scoped 12 KiB
stack after finding the prior 3,072-byte default, but the missing simultaneous serial trace means
this does not prove stack exhaustion. The retained `64062cd` candidate containing `f6f0d2d` then
passed app-only flash/digest/boot verification. One newly consented post-stack diagnostic sent
exactly one camera command with no automatic retry and ended after 45,091 ms at the same
`device_reconnected_or_disconnected` stage, with `capture_completed_events=0` and no upload. The
12 KiB mitigation did not resolve the physical failure. HW-12 remains NOT RUN; bounded
cause-discriminating diagnostics must precede any further newly consented attempt. No image was displayed, viewed, externally processed or retained.
A subsequent fresh approval authorized one content-free serial diagnostic. It sent exactly one
camera command with no automatic retry and ended after 45,016 ms with `panic_observed`, one boot/
reset window, no frame-copy marker and no completion or upload. This is consistent with a panic before the existing frame-copy marker,
but the bounded marker aggregation does not identify the exact panic site. No image was displayed, viewed, externally processed or retained.
HW-12 remains NOT RUN pending a tested stage-boundary diagnostic or correction.
A further fresh approval authorized one content-free backtrace diagnostic. It sent exactly one
camera command with no automatic retry and ended after 45,020 ms with one panic/reset window, no
frame-copy/error marker, completion or upload. Retained-ELF classification of nine bounded code
addresses was `shutter_audio_path`, narrowing the observed panic to shutter-sound playback before
camera dequeue/frame copy. The bounded result does not identify the exact faulting instruction and
exposed no exact addresses, raw symbols or raw serial. No image was displayed, viewed, externally processed or retained.
HW-12 remains NOT RUN pending a failing shutter-audio boundary test and the smallest correction.
After that correction was flashed and qualified, one newly consented post-correction command
completed authenticated capture/upload, JPEG validation, fetch and TTL purge with a stable
connection and no retained media. This makes HW-12 physical capture/upload PASS; the operator did
not hear a shutter sound or see a screen change. At that HW-12-only checkpoint, live Hermes image
interpretation remained pending under CAM-002; the later CAM-002 run above completed it.
Last updated 2026-09-04.

## Environment evidence

- Platform: Ubuntu 24.04.4 under WSL2; Python 3.12.3 and locked `uv` dependencies are available.
- ffmpeg 7.0.2-static, `libopus.so.0` and libsndfile are available.
- ESP-IDF v5.5.4 commit `735507283d5b2f9fb363a1901172dbd9e847945d`, CMake 3.28.3,
  Ninja 1.11.1, ESP32-S3 GCC 14.2.0 and esptool 4.12.0 are available after shell activation.
- Official StackChan Firmware 1.5.1 is present as a reviewed vendor snapshot with a project-owned
  component/HAL overlay. Exactly one K151/CoreS3 USB Serial/JTAG device was reviewed through WSL;
  live Hermes v0.20.0 text/Skill access is Green through loopback-only SSH forwarding.
- The user installed `usbipd-win` 5.3.0 on Windows to attach the device. No WSL OS package, shell
  profile, user Hermes configuration, secret or media artifact was changed. After backup and
  identity checks, the explicitly approved custom image and corrected applications were written.
  One explicitly approved WSL-specific firewall rule was created for bounded hardware sessions;
  it was retained throughout the continuous campaign and removed in final Goal cleanup. Windows
  default inbound remains Block and no broader rule was created. No erase-all or factory-restore
  command was executed. USB was detached and the temporary Bridge/TTS/Hermes connectivity was
  stopped after acceptance. The last pre-cleanup content-free preflight had found one stable serial
  identity and one enabled named rule with the approved inbound/TCP-8765/`LocalSubnet`/WSL-VM scope.

The tested host worktree establishes the source-backed motion boundary before any physical command.
K151 conservative motion profile: yaw `-45..45` degrees, pitch `5..85` degrees, speed
`1..30` (default `15`), home `0/45` degrees. Red→Green tests cover Firmware boundary/default/home
behavior, Bridge pre-send rejection, Control API error mapping, MCP schema limits, contract parity
and the narrowed official HAL adapter. The current device contains the motion-locked `d88f6df`
release with its Wi-Fi diagnostic disabled. The separately approved attended candidate
advertised `head=true`, kept its local-command lock on and completed the exact bounded yaw, pitch and
home sequence before the normal release was restored.

## TDD evidence

Representative Red → Green slices in the current worktree include:

| Slice | Initial Red | Current Green behavior |
| --- | --- | --- |
| Protocol and handshake | typed families/limits/transport absent | schemas and Pydantic agree; authenticated hello/ack and command/result run over real WebSocket |
| Gateway and capture | no registry/send/upload ownership | duplicate cleanup, bounded commands and authenticated mode-0600 JPEG lifecycle |
| Voice turn | no codec/VAD/provider/turn path | Opus→VAD→STT→Responses SSE→ordered TTS→Opus completes against Simulator |
| Hermes errors/progress | provider failures/tool events collapsed | 401/404/429/5xx/timeout/transport/SSE remain typed; thinking/idle notifications are paired |
| Camera and vision | no explicit image turn or safe fallback | capture→inline `input_image`→spoken response plus MCP ImageContent/fallback |
| Reconnect/faults | no backoff or selectable corruption | capped 1/2/4/8/16/30 sequence, stable reset and deterministic fault/event injection |
| Operations/privacy | no safe backup/report/service/debug-audio behavior | dry-run backup, bounded digest-verified region reads with retry, redacted report, restart backoff and opt-in TTL audio store |
| Firmware protocol/state | no project device peer | auth/hello, guarded parser, eight states, 256-ID duplicate cache and reconnect/session behavior pass host C++ tests |
| Firmware I/O integration | no custom board path | official HAL adapters provide NVS/USB settings, mDNS/fallback, commands, touch audio, bounded playback and finite camera upload |
| Firmware camera command ordering | a camera worker could start inside command handling and delay the command result past the Bridge deadline | a failing Firmware test preceded source commit `8bfc589`; the request is queued and the worker starts only from the later camera update phase after the network update |
| Bridge camera failure propagation | an owned `camera.completed(ok=false)` was ignored while the upload waiter ran until `CAPTURE_TIMEOUT`, and a broad ignore rule hid the production capture package | failing coordinator/event/package tests preceded `517011a`; ownership-safe failure wakeup maps to `CAPTURE_FAILED`, runtime wiring forwards the event, and only root private-output directories remain ignored |
| Firmware camera worker stack | one 3,072-byte default-stack `std::thread` performed capture, JPEG conversion and HTTP upload; the second diagnostic changed/disconnected before any completion or upload | a failing contract test preceded `f6f0d2d`; only the camera worker receives a scoped 12 KiB pthread configuration, the caller configuration is restored and setup failure closes the request. This is an evidence-based mitigation and does not prove stack exhaustion |
| Firmware safety | protocol-valid values were wider than the K151 physical profile and the adapter had no motion path | Bridge/MCP/Firmware now reject outside yaw `-45..45`, pitch `5..85` and speed `1..30`; home is `0/45`; the HAL narrows local angles and disables yaw PWM, while the release output lock remains enabled |
| Provisioning boot | zero-length line history was accepted by a contract test but rejected by ESP-IDF at runtime, followed by a panic/reset loop | a failing contract test requires the minimum valid one-entry RAM history and cleanup; the corrected Firmware reaches its provisioning prompt without panic/reset |
| Provisioning input | secondary USB console emitted the prompt but ESP-IDF defines that mode as output-only | a failing contract test requires primary USB Serial/JTAG console mode; physical Enter and invalid-command recovery are Green after commit `ab7f1e4` |
| Provisioning NVS key | physical `set-discovery disabled` aborted with `ESP_ERR_NVS_KEY_TOO_LONG` | a failing test enforces ESP-IDF's 15-byte NVS key limit; write/read use physical `bridge.discovery`, and the same physical command saves successfully after commit `a6c882e` |
| Optional command envelope | physical status command disconnected when absent optional fields were serialized as JSON `null` | a failing model test requires absent fields to be omitted; `model_dump_json(exclude_none=True)` preserves the protocol contract and physical status/info commands pass after commit `4abe3d9` |
| Hardware identity | the physical hello exposed the upstream network transport name instead of the K151 board model | a failing Firmware contract test requires one central K151 identity; hello/status/info now report `M5STACK-K151` after commit `0a3bad2` |
| Display routing | the launcher has no avatar view, so its chat-bubble call acknowledged without visible text | a failing contract test requires the board display adapter to use the global notification path after commit `b7b2830` |
| Display lifecycle | first global-toast use timed out, disconnected once and then reconnected | a failing contract test requires idempotent toast-manager initialization before the Bridge worker and Mooncake update; the physical command remains connected and visible after commit `6faa72e` |
| HW-04 visual observation | the generic smoke helper had no repeatable motion-free observation/restoration path | failing tests require a K151 with `head=false`, six non-motion apply/restore commands and best-effort remaining restores after one HTTP failure; repeated physical runs restored successfully, and brightness plus blue LEDs are now independently visible |
| Expression false success | the flashed launcher acknowledged happy while `SetEmotion()` discarded it because no avatar existed | a failing contract test requires `setExpression()` to initialize and verify the avatar and clear a deferred state overwrite before applying the emotion; `421457b` passes the focused/full contract suites and Firmware build, and its app-only flash/digest/boot plus operator-confirmed happy/idle path are Green |
| No-touch input activation | the production recognizer accepted one changed sensor sample as Press/Release; the comparison harness observed an input lifecycle while the operator touched nothing | an initial missing-header Red established startup qualification, then `stable touch did not emit a press` forced real transitions; `HeadTouchDebouncer` now requires stable idle and three consecutive press/release samples, with held-startup/transient-noise tests, 19/19 CTest and a fresh ESP-IDF build Green; app-only flash/digest/boot and the 60.03-second attended no-touch regression are physically Green |
| Corrected deliberate touch | no corrected physical press/release evidence existed after the no-touch defect fix | a separately consented 51.11-second production-Gateway observation accepted one approximately one-second touch/release, emitted one touch-to-silence lifecycle and stayed connected; 25 frames / 3,617 bytes were immediately discarded, completing HW-02 only |
| Touch observability | audio-frame/active-turn metrics could not distinguish a missing sensor event from a later microphone/turn failure | a failing event test requires label-free `touch_events_total`; idle, barge-in, shared-runtime and `/metrics` tests are Green after `c94efb5`. The physical head sensor is Green through its direct audio lifecycle, but that path emits no `touch.*`, so a physical counter increase remains pending |
| Reconnect observation | the previous Bridge stop/restart window had no defensible latency boundary | failing tests require initial connection, ignore one transient, confirm loss and measure to target ID/K151/head-lock re-registration under one deadline; final physical use measured 15,697.6 ms including a deliberate 3.0-second down hold and left display/reboot conclusions to independent evidence |
| Reconnect presentation | global state notifications first used an avatar speech path, then remained inside launcher-false avatar initialization | a first failing test added global notifications in `e73dc30`; after physical failure plus a visible manual toast isolated the remaining gate, a second failing test preceded launcher-independent notification state in `7913742`. Both toasts are now physically visible; lower-stack placement of `Connecting Bridge` remains a UX follow-up |
| Background turn failure | a failed detached voice turn emitted `Task exception was never retrieved` during physical Bridge shutdown | a failing audio-input test reproduces garbage collection of an unwaited failed task; `eef1390` retrieves each background result in a done callback while preserving explicit wait behavior |
| Coordinated signal shutdown | PTY Ctrl+C stopped the physical session but Uvicorn re-raised SIGINT before its peer lifespan finished and printed a cancellation traceback | a failing runtime test requires both server exit flags without signal re-raise; `85e2c2a` preserves exit 130, and an actual two-loopback-server Ctrl+C check exited 130 without a traceback |
| Backup discovery | a verified private backup one level below `firmware/backups` was incorrectly reported absent | a failing nested-backup test preceded bounded root/one-level non-symlink discovery in `708084b`; the actual backup now reports verified |
| Firmware provenance | official source/dependencies absent | source tree, MIT notice, six Git repositories, 60 managed component contents and ESP-IDF commit are locked and verified |
| Documentation | progress absent and stale phase claim | required documents and all 27 requirement IDs are contract-checked |

## Host quality gate

The current standalone `./scripts/verify-host.sh` and the host sub-gate of the final gate both
exited 0 with this evidence:

- `uv lock --check`: 104 packages resolved and the lock is current.
- `ruff format --check`: 154 files already formatted; `ruff check`: all checks passed.
- strict mypy: success across 61 source files.
- pytest: **433 tests passed in 35.02 seconds** in the current standalone host gate and
  **429 tests passed in 31.20 seconds** in the latest final combined gate. Historical evidence checkpoints
  remain recorded below rather than being promoted as current. The scoped-stack checkpoint had
  373 tests passed in 30.01 seconds; post-stack had 374 tests passed in 28.12 seconds; content-free
  serial had 375 tests passed in 28.01 seconds; and content-free backtrace had 376 tests passed in
  30.29 seconds.
- branch coverage: **85.32%** in the current standalone host gate and **85.32%** in the latest final
  combined gate; required threshold is a precise 85.00%.
- Protocol validation: **11 valid** and **8 expected-invalid** examples behaved correctly.
- secret scan: no new potential secrets across tracked and non-ignored untracked files. Its
  reviewed baseline contains only 44 public commit/hash, X.509 certificate and scanner-regex false
  positives; ignored dependency/build trees are provenance-checked separately.
- dependency audit: no known vulnerabilities (the editable local distribution is skipped by the
  audit tool, not the dependency set).
- offline doctor: Python, uv, Git, ffmpeg and libopus required checks available; CMake/Ninja
  available; `idf.py` not active in the host-only shell and Hermes explicitly missing as optional
  checks.

The current `./scripts/verify.sh` combined gate exited 0 with ESP-IDF v5.5.4 active. It repeated
the host gate, verified the locked Firmware inputs, passed every Firmware host test and built a
fresh Bridge-enabled image from the checked-in verification defaults. Running without the ESP-IDF
environment first stopped explicitly at the Firmware gate; no check was skipped.

Local Uvicorn/WebSocket tests require loopback sockets and event-loop portals that the managed
sandbox blocks. The unchanged commands are run with the provided local-execution approval; tests
are not skipped or weakened.

## Simulator and Mock evidence

- `./scripts/run-simulator-e2e.sh`: **exit 0; 9 passed in 1.90 seconds**.
- Actual Uvicorn Bridge and Device Simulator perform authenticated hello/ack, ping/pong,
  command/result, capture upload and registry cleanup.
- The complete voice integration streams generated PCM as Opus, uses Mock STT/Hermes/TTS, and
  reconstructs one ordered 16 kHz output stream. The full-flow fixture sent seven input packets and
  received non-empty output without committing a WAV fixture.
- Generated 320×240 JPEG data exercises capture and vision paths; no generated capture artifact is
  tracked.
  The deterministic explicit-vision result is `机の上にロボットがいます。`; this proves plumbing,
  not real visual accuracy.
- Mock Hermes exposes only public-style health/capability/model/discovery/Responses endpoints and
  deterministic SSE/tool/error/delay/disconnect surfaces.

## Firmware build and external evidence

- In an isolated review directory, the official host test passed 1/1 and unchanged `idf.py build`
  exited 0 for `esp32s3` with the locked source/dependencies.
- `stack-chan.bin`: 3,786,944 bytes; SHA-256
  `32abe637f2fb7f600c0a64cf2c8e06aad569bc0989a74140620c2e792d5174b2`; app partition had 27%
  free. Secure Boot and Flash Encryption were disabled in the baseline build configuration.
- Before integration, the imported workspace also recomputed all six Git and 59 baseline managed
  component identities. Its same-size app SHA-256 was
  `177b1c7e8c2a8f9fc6c4b55445808e70d96cd85f31f3e209f3d37cb51b310e9f`.
- The two app images differ in 72 bytes because official defaults embed app and bootloader compile
  times. Their partition-table and generated-assets hashes match; no bit-for-bit deterministic
  binary claim is made.
- Integrated dependency verification passes for six fetched Git repositories and 60 managed
  components (plus the IDF entry). The current Firmware host CTest suite passes **22/22**.
- A fresh Bridge-enabled/primary-USB/motion-locked ESP-IDF build exited 0. The historical retained
  `firmware/build-hermes-toast-init-6faa72e/stack-chan.bin` is **3,918,448 bytes**, SHA-256
  `ed581f4ad8374325729558233da2dbde329f58d5732e0254f3b2b5ad7e26dc79`, with **24%** of the
  smallest `0x4f0000` app partition free. Its partition table exactly matches the verified
  factory layout. It supplied the independently confirmed manual display baseline.
- The superseded first reconnect-presentation app
  `firmware/build-hermes-reconnect-toast-e73dc30/stack-chan.bin` is **3,918,512 bytes**, SHA-256
  `7828fa05e4dc8bdd840694050a5c1c24f3df43e3d468c43f0a52e26d4a223050`, with **24%** free. Its
  inspected configuration enables the Bridge client, primary USB Serial/JTAG console and
  `CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y`. It was physically flashed and digest-verified, but
  its reconnect notifications remained invisible behind launcher avatar initialization.
- The previous retained app from `7913742`,
  `firmware/build-hermes-reconnect-launcher-7913742/stack-chan.bin`, is **3,918,528 bytes**, SHA-256
  `ae5ced6a224c0991ff4d9164eec471341cb7b43404bb574762ba9aed9ba2d1a1`, with **24%** free. It is
  the reconnect-verified predecessor and matched an independent read-only device comparison
  immediately before the expression app replaced it.
- The latest final combined gate independently verified the K151 command-source isolation worktree
  in a temporary directory after 429 host tests passed in 31.20 seconds at 85.32% coverage and
  22/22 Firmware CTest passed. Its **3,920,800-byte** image had SHA-256
  `a446bd98c601764a66f4a0af548942c5f5e2881913bfcccd005d7e269684edf7` and **24%** partition
  headroom. The temporary sdkconfig was inspected during the build and contained
  `CONFIG_STACKCHAN_HERMES_BRIDGE_CLIENT=y`, `CONFIG_STACKCHAN_HERMES_USB_PROVISIONING=y`,
  `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y` and the gate-required
  `CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y`. The build output was deleted and not flashed; no
  physical head command was sent.
- Commit `83842148e8d95ad52a72de386cb4647c545dbaf4` has a separately retained and now flashed attended
  candidate at `firmware/build-hermes-motion-8384214/stack-chan.bin`: **3,921,232 bytes**, SHA-256
  `af98e32ce32aa21214d4c8e29440fb2785b1f2f020f405ae2e049a332ebd7d7d`, with **24%** headroom.
  Esptool reports valid checksum `0e` and validation hash
  `d0031034222b442d92e2c40b942d41f81d962641aa87ee1d7eb0b0d1a69eef0f`. Its generated config has
  Bridge, USB provisioning and primary USB Serial/JTAG enabled, global head motion unlocked, and
  `CONFIG_STACKCHAN_HERMES_LOCAL_MOTION_LOCK=y`. The candidate partition SHA-256 is the unchanged
  factory value `48da0866f56d9d8eb1fe786412984d8f1a4a01b3f13f965621fcb916761e1a4b`, byte comparison against
  the verified backup passed, and `app-flash_args` contains only `0x20000 stack-chan.bin`. Factory
  image and partition sidecars recomputed successfully. At the candidate-validation checkpoint
  nothing had been written and no motion command had been sent; flash and physical-motion approvals
  remain separate.
- The 2026-09-03 attended motion-candidate preflight then revalidated one free stable serial,
  private backup size/hash/permissions, factory-identical partition, candidate size/hash/internal
  image checks/config/app-only mapping, disabled Secure Boot and Flash Encryption, the current
  motion-locked app digest, one exact scoped firewall rule and zero 8765/8766 listeners. The device
  received esptool's final hard reset for normal boot; no post-reset boot qualification is claimed
  at this checkpoint. There was no flash write or physical head command; explicit flash approval
  remains pending.
- The 2026-09-03 attended motion-candidate app-only flash followed the later distinct explicit
  approval. The unique serial, verified backup, partition, security state and predecessor digest
  were revalidated, then only the 3,921,232-byte app was written at `0x20000`. The write hash and
  independent digest both matched. A 35.09-second content-suppressed boot window discarded 11,874
  serial bytes while counting one boot, one Firmware-version and two reset markers with zero panic,
  watchdog, stack, heap, brownout, camera-error, disconnect or reopen markers. Postflight retained
  one free stable serial, zero Windows/WSL listeners and the exact scoped firewall rule. No physical
  head command has been sent; authenticated capability recheck and physical motion approval remain
  pending.
- The 2026-09-03 attended initial K151 motion followed a fresh, distinct approval. A failing test
  first showed that the physical smoke helper treated HTTP-success/device-`ok=false` as success;
  `c033aff` made it fail closed, with 5/5 focused tests and the 418-test host gate Green. The
  content-suppressed live harness was independently Red→Green with 12/12 tests plus format, Ruff and
  strict mypy checks. Preflight reverified the unique serial, backup, candidate digest, one exact
  Hyper-V firewall rule, default inbound Block and zero listeners. A process-only token established
  the exact K151/Firmware `1.5.1`/`head=true`/IDLE session. Exactly one `head.set_angles` command used
  `yaw=5`, `pitch=45`, `speed=10`; no retry, follow-up or home command was sent. It was acknowledged
  with `motion_commands=1`, stable connection, final IDLE, 143 discarded serial bytes and zero
  device/servo, queue, input, touch, boot, reset, panic, watchdog, stack, heap, brownout,
  camera-error, disconnect or reopen markers. The operator observed motion, reported no abnormal
  sound, vibration or heat, and touched neither the device, desk nor cable. Postflight had one free
  stable serial and zero listeners/harnesses. The physical yaw/pitch/home sequence remains
  incomplete; no direction-specific result is inferred from the observed movement.
- The 2026-09-03 attended K151 home attempt followed another distinct approval. Its home-only
  harness was Red→Green with 15/15 tests plus format, Ruff and strict mypy checks. Preflight again
  passed unique-serial, backup, candidate-digest, scoped-firewall/default-Block and zero-listener
  gates. Exactly one `head.home` command was acknowledged with `motion_commands=1`,
  `home_commands=1`, `angle_commands=0`, stable connection and final IDLE; there was no retry or
  additional motion command. All device/servo, queue, touch and serial fault/reset counters were
  zero, but the 4,450 ms observation contained `input_starts=1`, `input_frames=41`, `input_ends=1`.
  The fail-closed result was therefore `machine_valid=false`. The operator did not observe movement
  because the head appeared already centered, reported no abnormal sound, vibration or heat, and
  touched neither the device, desk nor cable. No cause is assigned to the no-contact input lifecycle,
  and command acknowledgement is not position feedback; physical home remains unestablished.
  Postflight was clean and retained the scoped firewall rule for final Goal cleanup.
- The 2026-09-03 attended K151 positive-yaw observation followed a fresh distinct approval. Its
  yaw-only harness was Red→Green with 20/20 tests, format, Ruff and strict mypy Green, and the smoke
  helper was 8/8 Green. Unique serial, backup, candidate digest, firewall/default-Block,
  zero-listener, exact device identity, IDLE and pre-command audio/event/serial quiet gates all
  passed. It sent exactly one `head.set_angles` command with `yaw=10`, `pitch=45`, `speed=10` and no
  retry or home command. The result was `machine_valid=true`: `motion_commands=1`,
  `angle_commands=1`, `home_commands=0`, `exact_yaw_commands=1`, acknowledged success, stable
  connection, final IDLE, 337 discarded serial bytes, `input_starts=0`, `input_frames=0`,
  `input_ends=0` and zero fault/touch/reset/reconnect counters. The operator observed the face move
  slightly to the left when viewed from the front, reported no abnormal sound, vibration or heat,
  and touched neither the device, desk nor cable. Postflight was clean. The positive yaw direction
  is physically established; pitch and home remain unestablished, and return-home still requires a
  separate approval.
- The 2026-09-03 attended K151 return-home observation consumed that separate approval from the
  machine-verified positive-yaw offset. The live harness evolved Red→Green to 52/52 tests, with
  format, Ruff and strict mypy Green; its bounded readback correction accounted for servo
  quantization while rejecting positions outside ±2 degrees. All earlier starts safely stopped
  before any motion command. The final armed run released one `head.home`; the operator observed a
  rightward return to center, confirmed the centered result, reported no abnormality and touched
  neither the device, desk nor cable. Its result collector then returned `unexpected_error` and
  `machine_valid=false`, so acknowledgement and complete runtime counters are not inferred. A
  distinct stdin-closed read-only follow-up returned `position_home=true` and
  `position_offset=false` without reaching the motion path. Therefore physical return-to-home
  motion was observed, but machine-valid home completion remains unestablished. Postflight was one
  serial, zero Windows/WSL listeners, zero harnesses and the same one narrowly scoped Hyper-V rule
  retained for final Goal cleanup.
- The 2026-09-03 attended K151 pitch observation followed another distinct approval from the
  read-only-confirmed home position. Its pitch-only harness reached 61/61 Red→Green tests plus
  format, Ruff and strict mypy Green; the hardware-smoke helper was 8/8 Green. Unique serial,
  backup, candidate digest, exact firewall/default-Block, zero-listener, exact identity, IDLE,
  bounded home-position and pre-command quiet gates passed. It sent exactly one
  `head.set_angles` with `yaw=0`, `pitch=40`, `speed=10` and no retry or home command. The result was
  `machine_valid=true`: `motion_commands=1`, `angle_commands=1`, `home_commands=0`,
  `exact_pitch_commands=1`, acknowledged success, stable connection, final IDLE,
  `initial_pitch=45.3`, `final_pitch=40.3`, 143 discarded serial bytes and zero
  input/touch/fault/reset/reconnect/backtrace evidence. The operator observed the head move downward
  when viewed from the front, reported no abnormal sound, vibration or heat, and touched neither the
  device, desk nor cable. Postflight was one serial, zero Windows/WSL listeners/harnesses and the
  same scoped rule. The decreasing pitch direction is physically established; machine-valid home
  completion remains unestablished, so HW-04 stays PARTIAL.
- The 2026-09-03 attended K151 machine-valid home followed a final distinct approval from measured
  pitch 40.3 degrees. Its home-only harness was developed Red→Green with 57/57 tests plus format,
  Ruff and strict mypy Green; the existing smoke helper was 8/8 Green. Unique serial, verified
  backup, candidate digest, exact firewall/default-Block, zero-listener, exact identity, IDLE,
  bounded pitch-offset and pre-command quiet gates passed. It sent one `head.home` and no retry or
  additional motion command. The result was `machine_valid=true`, `motion_commands=1`,
  `home_commands=1`, `angle_commands=0`, `exact_home_commands=1`, acknowledged success, stable
  connection and final IDLE. Three reads measured pitch 40.3 before and 44.3 after the command,
  with final yaw 0.6 degrees inside the configured home tolerance. Input, touch, fault, reset,
  reconnect and backtrace evidence was zero. The operator saw one upward movement, reported no
  abnormal sound, vibration or heat, and touched neither the device, desk nor cable. Fine-angle
  arrival was not independently judged by eye; the measured final position supplies that evidence,
  and no second physical movement was expected. Postflight retained one serial, zero Windows/WSL
  listeners and harnesses, one exact scoped rule and default inbound Block. Thus machine-valid home
  completion is established and HW-04 is PASS; earlier failed-closed attempts remain historical.
- After the expression correction, `./scripts/verify-firmware.sh` again verified all six fetched
  repositories, all 60 managed components and Firmware CTest **18/18**, then built a fresh
  Bridge-enabled image from `421457b`. The temporary app was **3,918,576 bytes**, SHA-256
  `4dd63efe2599ef42d37d40a3fa2002101bb917fe0f78ab6a24531ec27da90901`, with **24%** free. This is
  build evidence only; it was deleted by the gate and never flashed.
- Committed HEAD `bd49497` was then retained as
  `firmware/build-hermes-expression-bd49497/stack-chan.bin`: **3,918,576 bytes**, SHA-256
  `78d200403f9d028b690cc50f1d1f7e7d69007c517164506d7f2b09ac5b0ebb2b`, with **24%** free.
  Esptool reported a valid checksum and validation hash. Its generated configuration enables the
  Bridge client, USB provisioning, primary USB Serial/JTAG console and physical head-motion lock;
  Secure Boot and Flash Encryption remain disabled. Its partition table is byte-identical to the
  previous retained build, and `app-flash_args` contains only `0x20000 stack-chan.bin`. It became
  the independently verified predecessor to the no-touch correction below.
- The no-touch correction was retained from source HEAD `fffaba3` as
  `firmware/build-hermes-head-touch-fffaba3/stack-chan.bin`: **3,918,672 bytes**, SHA-256
  `cf122cd787fae325e38ba3caa2b743e2c4386559d2e46f94e93333d69f8e4551`, with **24%** free.
  Esptool reports checksum `5c` and validation hash
  `0ab620c4287c089b2eae2c918faa4f4ff237dcefa35a5ceb2a814bdaceacfe9f`, both valid. The retained
  mode-0600 sdkconfig has SHA-256
  `ad8eff6046d13a834e900e0e250f9e3a04f1cf35c0ebcaee68c0ae00acff3869`; Bridge, USB
  provisioning, primary USB Serial/JTAG and the physical head-motion lock are enabled, while Secure
  Boot and Flash Encryption remain disabled. Its partition-table SHA-256 is the unchanged
  `48da0866f56d9d8eb1fe786412984d8f1a4a01b3f13f965621fcb916761e1a4b`, and the app argument has
  `0x20000 stack-chan.bin` only. This is now the current physically flashed and independently
  digest-verified app; its attended behavioral no-touch regression is also Green.
- `verify-firmware.sh` now creates a fresh temporary sdkconfig from
  `sdkconfig.hermes.defaults`, so an ignored local setting cannot disable the behavior being
  verified. It explicitly rejects a generated config without the physical motion lock, then
  emits image size and SHA before deleting its temporary build directory.
- Live Hermes/STT/TTS: **NOT RUN**; no endpoint, API key or provider is available.
- HW-01: **PASS** on 2026-08-30. Factory Firmware `1.4.4` booted on an ESP32-S3 rev 0.2 with
  16 MiB QIO flash and 8 MiB PSRAM. Secure Boot and Flash Encryption were disabled. The boot log
  and ESP-IDF parser agreed on all seven partition entries.
- The factory image is exactly 16,777,216 bytes. Sixteen independently digest-verified 1 MiB
  reads completed with zero retries, stored SHA-256 sidecars recomputed successfully, and a final
  read-only whole-device `verify_flash` digest comparison matched. The image, raw identity,
  metadata and boot log remain mode-`0600` ignored local evidence.
- The same read-only whole-device comparison still matched immediately before the approved first
  write. The generated configuration retained Bridge client, USB provisioning and
  `CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y`; the generated partition table remained
  byte-identical to factory.
- The first retained custom application, SHA-256
  `cbfb346d603b5b82c8d1ed68ee734ff5cfab251d038bbf64d65d90853117090d`, was written through its
  generated esptool `@flash_args`; bootloader, application, partition table and assets passed
  post-write hash checks. Its first boot nevertheless exposed an ESP-IDF provisioning-console
  defect: a zero-length history setting was rejected and cleanup entered a `LoadProhibited`
  panic/reset loop. The run was rejected and the device was halted in the ROM downloader instead
  of being left looping.
- Red→Green commit `fca58cf` added a failing contract test, used the minimum valid one-entry RAM
  history and explicitly freed history. The full combined gate then passed. Because all other
  retained artifacts were unchanged, only the corrected application was reflashed; a read-only
  application `verify_flash` digest comparison matched afterward.
- A 35-second serial observation after an official reset saw exactly one custom Firmware `1.5.1`
  boot and no ROM boot, software reset, panic, `LoadProhibited`, provisioning-start failure or
  watchdog marker. Later 45/50-second redacted observations of the current image again saw one
  boot without panic/abort/watchdog. These windows prove stable observation, not latency or
  physical I/O quality.
- Physical USB input produced the prompt and usage error/recovery. Five runtime settings were
  saved without printing or storing the random token on the host. The current Firmware's
  line editor can echo typed input; therefore the token was sent through a response-suppressing
  serial utility, not a recorded monitor session.
- Physical Wi-Fi station startup and IP acquisition were observed on the same `/24` as the Bridge
  host, without config mode. The first Bridge attempt stopped before WebSocket with errno 113;
  read-only checks identified mirrored mode, Hyper-V default inbound Block and no TCP 8765 rule.
- After explicit approval, one rule named `StackChanHermesBridge8765` was created with inbound
  Allow restricted to TCP 8765, `LocalSubnet` and the WSL Hyper-V VM creator. Default inbound
  remained Block. Earlier sessions removed it afterward; the current continuous-test instruction
  instead retains exactly one scoped copy until final Goal cleanup. Idle checks find no Bridge
  process and no listener on 8765/8766.
- The corrected application was flashed only at `ota_0@0x20000`; esptool's post-write hash and an
  independent read-only `verify_flash` digest comparison passed. Bootloader, partition table, NVS
  and assets were not rewritten. A 20-second nonprinting serial observation saw no panic, abort,
  watchdog or reboot-loop marker; the window is not a latency measurement.
- A physical authenticated hello registered one device as Firmware `1.5.1`, hardware model
  `M5STACK-K151`, with microphone/speaker/camera/touch/display/avatar true, 12 LEDs and head false.
  `device.get_status` and `device.get_info` each returned HTTP 200 with `ok=true`; both retained the
  K151 identity and the device remained connected. This completes HW-03.
- The launcher has no avatar view, so a failing contract test first moved `display.show_text` from
  its avatar-only bubble to a global toast in `b7b2830`. The first physical global-toast command
  timed out, disconnected once and automatically reconnected. Review strongly implicated lazy
  ability creation during Mooncake's manager update, but no serial panic evidence was collected.
- A second failing contract test required idempotent toast-manager initialization before the
  Bridge worker and first Mooncake update. Commit `6faa72e` passed the complete gate with 332
  Python tests, 18/18 Firmware CTest targets and a clean ESP-IDF build. After explicit approval,
  its retained 3,918,448-byte application was written only at `ota_0@0x20000`; the post-write hash
  and an independent read-only `verify_flash` matched. Bootloader, partition table, NVS and assets
  were untouched.
- In the final observed session, `display.show_text` for `HERMES OK 0831` returned HTTP 200 with
  `ok=true` in 174 ms and the operator independently confirmed the text on the physical LCD.
  Connected devices stayed at one and both disconnect and command-timeout counters stayed zero
  through the following 20-second observation. The value is not presented as latency evidence.
  A separate touch prompt still produced no audio frame or active turn, so touch remained unverified
  at that checkpoint. The corrected deliberate-touch observation below later superseded this failed
  prompt and completed HW-02.
- An initial observer attempt returned 2237.4 ms, but the replacement Bridge exited because its
  orchestration lacked a retained TTY. That value was rejected and is not performance evidence.
  A fresh authenticated session was then established.
- The first valid controlled HW-05 baseline confirmed loss twice, deliberately held the Bridge
  down for 3.0 seconds and used a TTY-held replacement plus the GET-only observer. The same target
  re-registered as `M5STACK-K151` with `head=false`; the observer measured **4052.5 ms** including
  that hold. A simultaneous sparse serial window saw no reset marker, but the operator saw no
  display change.
- A failing test then preceded the global `Connecting Bridge` and `Bridge connected` notifications
  in `e73dc30`. After explicit approval, its exact 3,918,512-byte/SHA-256 candidate, private stable
  identity, factory backup, motion lock and one-entry `0x20000` app definition were revalidated.
  The prior app matched read-only, only the app was written, and both the esptool post-write hash
  and independent digest comparison passed. A stable 30-second Firmware `1.5.1` boot window saw no
  panic/watchdog/reboot-loop marker.
- The `e73dc30` controlled run confirmed loss twice and recovered the same K151/`head=false` in
  **9461.9 ms**, including its 3.0-second hold. A simultaneous 183-byte serial window saw no
  ROM/reset/panic/watchdog marker, but the operator saw neither toast. A corrected 30-second manual
  `DISPLAY PATH OK` toast was then independently visible, proving the global display path while
  isolating state invocation.
- Review found both notifications were still gated by `IsSetupUICalled()`, which remains false in
  the launcher. A new failing contract test preceded the independent notification dirty flag in
  `7913742`; avatar-only presentation remains behind the original guard. Focused tests passed
  23/23, the complete gate passed 343 host tests plus 18/18 Firmware tests, and the fresh app had
  24% partition headroom.
- After a separate explicit approval, the retained 3,918,528-byte app with SHA-256
  `ae5ced6a224c0991ff4d9164eec471341cb7b43404bb574762ba9aed9ba2d1a1` passed the same one-device,
  identity, backup, configuration, app-only and unused-port guards. The current `e73dc30` app
  matched read-only before only `ota_0@0x20000` was written. Post-write hash and independent digest
  checks passed. A deliberate-reset 30-second serial window saw Firmware `1.5.1` once, the one
  expected ROM/reset sequence, and no panic, watchdog or further reboot marker.
- The final controlled run began with one K151/`head=false` and zero disconnect, auth-failure,
  timeout, touch, audio and active-turn metrics. It confirmed loss twice and measured
  **15,697.6 ms** to the same target's re-registration, including the deliberate 3.0-second hold.
  A simultaneous 25-second/186-byte serial window saw no ROM, reset, panic or watchdog marker.
  The operator independently saw both required toasts. `Connecting Bridge` was lower in the toast
  stack rather than replacing the top toast; that placement is a UX follow-up, while HW-05 is
  **PASS** within the bounded observation.
- Eight safe non-motion commands set and restored avatar expression, a dim blue LED state,
  brightness and volume. All returned HTTP 200 with `ok=true` while connectivity remained stable.
  Their visual/acoustic effects were not independently confirmed. No servo/head command was sent,
  `head=false` remained advertised, and the physical output lock remained enabled; HW-04 is
  **PARTIAL**.
- The dedicated attended safe-visual run subsequently applied happy, dim blue `(0,16,64)` and
  brightness 35 for 20 seconds, then restored brightness 70, cleared the LEDs and restored idle.
  It exited 0 with one connected device and zero disconnect/timeout/touch/audio-input/active-turn
  counters. The operator did not confirm seeing the effects, so HW-04 remains **PARTIAL**.
- A later bounded session first provisioned a replacement random token through a
  response-suppressing serial path. Its initial reset attempt never registered a device, so it was
  rejected and no body command was sent. A read-only esptool `flash_id` with default/hard reset
  then returned one Firmware `1.5.1` K151 with display/touch/avatar true and `head=false`.
- The safe visual sequence ran for 45 seconds and was repeated for 30 seconds when the first window
  was missed. Both runs applied happy, dim blue `(0,16,64)` and brightness 35, then restored
  brightness 70, cleared LEDs and restored idle. Every restoration was attempted and both runs
  exited 0. Connected-device count was one; disconnect, authentication-failure, command-timeout,
  touch, audio-input/output and active-turn counters were zero. No head, camera, microphone or
  playback command was sent.
- The operator saw the screen brightness change and blue LEDs during the repeated run, completing
  those two physical effects. Happy was not recognizable. Review proved this was not merely a
  missed observation: the flashed launcher left `IsSetupUICalled()` and `hasAvatar()` false,
  `setExpression()` returned true, and `SetEmotion()` returned without changing the display.
- A new failing contract test preceded commit `421457b`, which initializes the avatar only on an
  explicit expression command, verifies it exists, and clears the pending bridge-state
  presentation before applying happy. Focused/full contract tests, 18/18 Firmware CTest and the
  fresh ESP-IDF build are Green.
- On 2026-09-01, explicit approval preceded the retained expression app's one-device preflight.
  The 16 MiB backup and partition hashes recomputed successfully; target security remained Secure
  Boot/Flash Encryption disabled with crypt count zero; required USB/Bridge/motion-lock settings
  and the byte-identical partition table remained present; and read-only `verify_flash` matched
  the current 3,918,528-byte `7913742` app before any write.
- Only the retained 3,918,576-byte expression app was written at `ota_0@0x20000`; esptool's write
  hash and a separate read-only candidate comparison both matched. Bootloader, partition table,
  NVS and assets were untouched. Preliminary nonprinting observers without a boot marker were
  rejected, and their one exact stale monitor lock was terminated. The accepted exclusive
  30-second deliberate-reset window captured 13,086 bytes, one Firmware `1.5.1`, one expected
  ROM/reset pair and zero Guru Meditation, LoadProhibited, abort and watchdog markers.
- A separately approved hardware-only Bridge session used a fresh response-suppressed token and
  the exact temporary WSL/LocalSubnet/TCP-8765 rule. No live Hermes request was possible. One
  authenticated K151 advertised avatar/display, 12 LEDs and `head=false`; connected devices was
  one and disconnect/auth-failure/timeout/touch/audio-input/active-turn metrics were zero. After
  a five-second lead-in, happy alone was applied for 20 seconds and restored to idle in `finally`;
  both returned `ok=true`, the operator saw the happy eyes, and the same metrics remained Green.
  No LED, brightness, volume, head, camera, microphone or playback command was sent in this run.
  Expression was physically Green at that checkpoint; comparative volume was confirmed in the later
  run below, so HW-04 now stays **PARTIAL** only for safely bounded motion.
- The first attempted fixed-Japanese stimuli were invalid: Windows PowerShell 5.1 decoded a
  BOM-less UTF-8 script through an ANSI code page, turning its literal Japanese into mojibake before
  synthesis. Their inaudible or unintelligible results are therefore rejected as language-content
  evidence and did not establish a product-code defect.
- A two-beep control then exercised the physical decoder/resampler/I2S/internal-speaker path twice;
  both beeps were heard on both plays, state returned to IDLE and all transport, underflow, overflow,
  codec and device-error indicators remained zero.
- The replacement source constructed `こんにちは。` from explicit Unicode code points. The final
  57,678-byte, mono PCM16, 16 kHz/1.8-second candidate had SHA-256
  `ffb45d626fcbf1c15058dd839658fd27535b64d8a9dea5ce226e526975346148`. Windows Japanese recognition
  returned exactly `こんにちは` after processing with confidence `0.9625`; host Opus round-trip
  validation completed all 30 frames without codec errors.
- The exact candidate was sent once to one authenticated K151/Firmware `1.5.1` with `head=false`.
  Volume changed `70 → 85 → 70`; all 30 frames played, the device logged resampling and output
  enable, state returned to IDLE, and disconnect/authentication/timeout/underflow/overflow/device-
  error/touch/audio-input/active-turn counters remained zero. When prompted about content, the
  initial syllable and clipping, the operator reported it properly audible and reported no defect.
  HW-06 audio output is PASS. Temporary media/scripts were deleted and no production-code change
  was needed because the isolated defect was the test-stimulus encoding.
- A later motion-free comparison generated one deterministic 25-frame, 1.5-second two-beep Opus
  stream and reused the exact packet sequence at volume 45 then 85. Both post-playback states were
  IDLE, volume restored 70, the operator heard the comparison, and serial evidence showed expected
  resampling/output/volume actions with zero transport, protocol, codec, playback, panic or watchdog
  errors. The operator later confirmed that the second volume-85 play was clearly louder than the
  first volume-45 play, making comparative volume Green; HW-04 remains PARTIAL only for motion.
- That harness rejected its overall result after one `audio.input.start` / `audio.input.end` pair.
  The Firmware's physical head-sensor path emits this pair directly for Press/Release, and the
  operator confirmed touching nothing. No incoming audio content was saved, printed, transcribed or
  analyzed. Volume 70 was restored, the listener stopped, USB returned to `Shared`, temporary files
  were deleted and the runtime token was discarded; the approved firewall rule remains until final
  Goal cleanup.
- Commit `e19098d` added startup-idle qualification and a three-sample `HeadTouchDebouncer`, wired
  ahead of gesture emission while retaining the configured intensity threshold. Startup activation,
  one/two-sample noise, stable press/release and duplicate suppression tests pass. The isolated
  Firmware gate verified six locked repositories, 60 managed components and 19/19 CTest, then built
  a fresh motion-locked image of 3,918,672 bytes with 24% free and SHA-256
  `f35c24a94d20860d0a709973828035920997e38b1ed934a6d1fbbf3bcc54e43d`. That temporary image was not
  flashed; the retained image above was flashed later. The quiet no-touch window is now Green;
  the corrected deliberate-touch follow-up below is also Green, while full microphone acceptance
  remains separate.
- The final combined `./scripts/verify.sh` gate repeated all 352 host tests, verified 19/19 Firmware
  CTest targets and built another 3,918,672-byte motion-locked image with 24% free and SHA-256
  `391d06617aab21bc2e1106faec8ce5d872bcc4bc3217e80dcea1699cbd4bf39a`; it was temporary build
  evidence and was not flashed.
- The attended read-only update preflight then reconfirmed one stable serial identity; one complete
  16 MiB factory backup with matching image/partition sidecars, restore metadata and pre-flash boot
  log; ESP32-S3 rev 0.2; Secure Boot disabled; `SPI_BOOT_CRYPT_CNT=0`; and Flash Encryption
  disabled. The current expression app still matched its retained digest. The new candidate's
  SHA-256, factory-identical partition table, single `0x20000 stack-chan.bin` entry, Bridge/USB/
  motion-lock configuration and inclusion of `e19098d` in source HEAD `fffaba3` all revalidated.
  At that checkpoint no write command had been executed.
- The app-only flash was then explicitly approved. Esptool wrote the 3,918,672-byte candidate only
  at `ota_0@0x20000` in 19.9 seconds, leaving bootloader, partition table, NVS and assets untouched;
  its write hash passed. A separate read-only comparison reported `verify OK (digest matched)`.
  The following content-suppressed 30-second reset/boot observation counted 12,679 bytes, one
  Firmware `1.5.1` marker and two reset markers with zero panic, abort or watchdog markers. The
  temporary observer was deleted. This proves image integrity and boot health; the independent
  no-touch behavior check follows below.
- In the separately consented physical regression, preliminary token-provisioning attempts stopped
  before any listener-backed observation. A content-suppressed invalid-command probe isolated `LF`
  line handling and the need to wait for the REPL prompt; the successful attempt then provisioned a
  process-only token without printing or saving it and used a read-only `flash_id` reset.
- One authenticated `M5STACK-K151` / Firmware `1.5.1` connection with `head=false` stayed stable for
  60.03 seconds and reported `quiet=true`.
  The operator confirmed touching neither the device, desk nor cable.
  The observation confirmed that audio-input start/end, frames, discarded bytes and device events all remained zero, so no audio
  content was received, saved, printed, transcribed or analyzed. No playback, body, camera or head
  command was sent. The no-touch regression is physically Green; it did not by itself establish a
  deliberate touch or HW-07.
- Post-observation cleanup returned the listener count to zero, kept exactly one serial identity,
  deleted temporary source/test/probe files and bytecode, and discarded the process-only token. USB
  remained attached for the following approved deliberate-touch check; the scoped firewall rule remains until
  final Goal cleanup.
- The separately consented production-Gateway follow-up authenticated the same model/Firmware with
  `head=false` and remained connection-stable for 51.11 seconds with zero input disconnects and zero
  device events. The operator confirmed one approximately one-second touch/release and no speech.
  The direct head-sensor path produced one `touch` start and one `silence` end;
  25 Opus frames and 3,617 bytes were counted and immediately discarded. The observer reported
  `single_touch_green=true`, `trigger_touch=true` and `end_reason_silence=true`.
- No audio content was saved, printed, replayed, transcribed or analyzed. No playback, body, camera
  or head command was sent. Observer/runner/test sources and bytecode were deleted, the process-only
  token was discarded, the serial identity remained unique, and listener count returned to zero.
  The user-confirmed operation and bounded lifecycle complete HW-02. At that checkpoint HW-07
  remained NOT RUN because no WAV, volume/noise, spoken ending or maximum-duration stop was
  evaluated.
- The first separately approved HW-07 harness attempt used a 90-second attended-response timeout
  and stopped before the user's later action. It had no accepted audio result or WAV and is rejected.
  A failing harness test then required at least 600 seconds for each attended response before the
  synthetic capture, cleanup, formatting, lint and type checks returned Green.
- The accepted retry authenticated one stable `M5STACK-K151` / Firmware `1.5.1` with
  `microphone=true` and `head=false`; a five-second no-touch pre-signal window was quiet. Short
  speech delivered 68 Opus frames / 9,946 bytes over 4.08 seconds. Its mode-`0600` WAV was
  reconstructed, reopened and numerically analyzed: full/speech/noise RMS 553.8172/1996.7531/
  123.1321, peak 12012, SNR 24.1991 dB, 400 ms accepted speech, zero decode errors, Green volume,
  noise and clipping thresholds, and a VAD `silence` end.
- The separate intentionally silent held-touch path delivered 248 Opus frames / 36,329 bytes over
  14.88 seconds and stopped for `max_duration`.
  The operator confirmed approximately 20 seconds of touch, no speech and a final release.
  Its reopened mode-`0600` WAV had noise RMS 116.5341 and zero decode errors. Its expected
  `vad_accepted=false` / `volume_ok=false` are not treated as speech-quality failures. Peak 32767
  prevents any claim of zero clipped samples; `clipping_ok=true` only records the configured
  clipping-fraction threshold.
- Both private WAVs were cleared and immediately deleted (`wav_deleted=true`); session cleanup
  reported `private_files_remaining=0`, no listener on 8765/8766 and `hw07_green=true`. There was
  no replay, transcription, external service, cloud service or Hermes processing. Temporary
  sources/bytecode and the process-only token were removed, while the single scoped firewall rule
  remains retained until final Goal cleanup.
- HW-11's first physical candidate exposed cancellation/completion races before acceptance.
  Failing tests preceded `5bcabc8`, which includes in-flight physical output in completion, and
  source commit `e824ef4`, which resets the decoder for every new playback, generation-invalidates
  an in-flight decode on cancellation and rejects the stale decoded result. `./scripts/verify-host.sh`
  reported 363 tests passed after this documentation slice, and the complete `./scripts/verify.sh` gate,
  dependency locks, fresh ESP-IDF build and 20/20 Firmware CTest were Green.
- The retained, now-flashed candidate is
  `firmware/build-hermes-hw11-e824ef4/stack-chan.bin`, 3,919,184 bytes, SHA-256
  `6167fec5380d78fbc6026d6a931169e1f39d0dd5eef12a9897a84f393860cfec`, with 24% app free.
  One stable serial identity, the verified 16 MiB backup, unchanged partition/security state,
  checksum/validation hash and required Bridge/primary-USB/provisioning/motion-lock configuration
  passed preflight. The explicitly approved app-only `0x20000` write passed esptool's write hash and
  independent `verify_flash`; a 12,494-byte 30-second boot observation had the expected single app
  marker and zero panic/abort/watchdog/assert markers.
- Two fail-closed diagnostics were not promoted. The second 440 Hz stimulus was machine-complete
  but physically inaudible when isolated; that no-contact probe also produced one input start,
  44 frames and one input end, all immediately discarded without persistence or processing. A
  historical intermittent no-contact input-safety finding therefore remains; no cause is inferred
  from this single observation. A
  replacement 880/880 Hz run was physically correct but reported one still-unclassified queue
  event. The diagnostic harness then gained tested separate underrun and overflow counters.
- The accepted 880/880 Hz run sent 30 first-turn frames, began the cancel request approximately
  678 ms after host streaming started, completed it with `cancel_after_ms=1957.6` and 1279.7 ms
  cancel latency, confirmed IDLE, waited 1250 ms, then sent 20 frames under a distinct new turn.
  The second turn entered `SPEAKING`, completed and returned IDLE. Connection/authentication stayed
  stable and underrun, overflow, device-error and input start/frame/end counters were all zero. The
  operator heard a short first beep followed by a longer second beep and confirmed touching neither
  the device, desk nor cable. Machine and independent physical evidence therefore make HW-11 PASS.
- The separately attended bounded silent/440/880 comparison then ran six 1.2-second, 20-frame phases
  in counterbalanced order. Every phase started IDLE, entered `SPEAKING`, returned IDLE and kept the
  authenticated connection stable; input starts, frames and ends all remained zero, as did touch,
  underrun, overflow, queue and device-error counts.
  The operator heard two separated 880 Hz tones and confirmed touching neither the device, desk nor cable.
  No incoming media existed, and nothing
  was persisted or externally processed. The historical intermittent no-contact input-safety
  finding was not reproduced in this bounded comparison; the bounded input-safety follow-up is
  Green without inferring a cause or permanent correction. The first attended wait had timed out
  before sending any stimulus; its tested asynchronous 60-minute replacement preceded this accepted
  retry. WSL and Windows listener counts were zero afterward.
- The first Bridge shutdown surfaced an already-failed voice-turn background task as
  `Task exception was never retrieved`. No audio command was issued, debug persistence was off,
  no media was retained and the placeholder configuration stopped before a live provider request;
  this is not claimed as touch/audio evidence. A failing test reproduced disposal of an unwaited
  failed task before `eef1390` added result retrieval. The related 13-test suite is Green.
- Process-only random credentials were never printed or saved. At that earlier checkpoint, no
  camera command was sent without separate explicit privacy consent. The unsolicited lifecycle
  above retained no content
  and remains defect history rather than acceptance; the distinct consented session supplies HW-07
  evidence. At that earlier checkpoint, HW-08〜HW-10 and the then-unrun HW-12/HW-13 scenarios had
  not yet been executed; later sections supersede the HW-12/HW-13 status. Live Hermes/STT/TTS and
  camera behavior are not inferred from initialization, capability flags or command acknowledgements.
- Final physical reconnect observation: **15,697.6 ms including a deliberate 3.0-second down
  hold**. Earlier diagnostic intervals were 4052.5 ms before notification fixes and 9461.9 ms for
  the physically rejected `e73dc30` presentation.
  Command, audio, voice and live-provider latency remain unmeasured; deterministic Mock durations
  are not reported as physical performance.
- The currently flashed cancellation-corrected app matches its retained `e824ef4` candidate
  independently; the predecessor no-touch app matched immediately before the app-only write.
  The session ended with the Bridge/listener and session-temporary-target counts at zero, default
  inbound Block, and USB attached for the next approved hardware check. Exactly one approved narrow firewall
  rule is retained until final Goal cleanup; there is no listener on 8765/8766 while idle.

- The retained HW-12 ordering candidate is
  `firmware/build-hermes-hw12-8bfc589/stack-chan.bin`, 3,919,344 bytes, SHA-256
  `319006f5c9aa0ed06eb2de906c3da43a1aa022c9606789e816b0044124d6cd60`, from source commit
  `8bfc589`. Its explicitly approved app-only write and independent digest verification passed. A
  content-suppressed 30-second deliberate-reset observation captured 12,627 bytes with expected
  ROM/reset/project/version markers and zero panic, watchdog or assert markers.
- One separately consented production Control/Gateway request used quality 70, bounded expected
  dimensions/size and nonpersistent capture storage. The command result arrived, replacing the
  predecessor's five-second `COMMAND_TIMEOUT`, but no upload completed before the 45-second
  `CAPTURE_TIMEOUT`. That is physical evidence for the ordering fix only. It is not camera
  acceptance, and there was no retry.
- No image was displayed, viewed, externally processed or retained. The run did not print or save
  image content, capture identifiers, image hashes or credentials; no Hermes, STT, TTS or external
  image processor was used, and no capture media remained.
- A Red coordinator/event test then reproduced that an owned `camera.completed(ok=false)` did not
  interrupt the upload wait. Commit `517011a` maps the owned failure to `CAPTURE_FAILED`, protects
  reservations from another device, wires the runtime event path, and corrects root ignore rules so
  the capture source package is tracked. Its focused suite and current host checkpoint are Green:
  369 tests passed in 28.69 seconds with 85.26% coverage, plus formatting, Ruff, strict mypy,
  protocol examples, secret scan, dependency audit and offline doctor. HW-12 remains NOT RUN; one
  new explicit consent is needed for the stage-only diagnostic retry. The subsequent evidence-
  contract gate also passed: 370 tests in 29.20 seconds at the same 85.26% coverage.
- A second fresh explicit consent authorized exactly one further production request and was consumed
  by that request; no retry was sent. It returned HTTP 504 `CAPTURE_TIMEOUT` after 45,227 ms with
  failure stage `device_reconnected_or_disconnected`, `capture_completed_events=0`, zero capture/
  upload and failure metrics, no queue/device/input/touch event and an unstable original connection.
  No Firmware completion or Gateway upload was observed. No image was displayed, viewed, externally processed or retained.
  No image bytes, exact hash or identifier were emitted; zero owned capture media remained, and
  postflight again found one idle serial device, no listener and exactly one retained scoped rule.
- Static inspection then established that the camera's capture/JPEG/HTTP path shared one
  ESP-IDF `std::thread` with the 3,072-byte default stack. The connection change is consistent with
  stack exhaustion, but without a simultaneous serial trace it does not prove stack exhaustion.
  A Red Firmware contract preceded `f6f0d2d`: the camera worker alone now receives a 12 KiB
  ESP-pthread stack, the caller configuration is restored immediately after thread creation, and
  configuration failure produces an internal-error completion instead of starting the worker.
- `./scripts/verify.sh` at the `f6f0d2d` source checkpoint exited 0: 371 tests passed at 85.20%
  coverage, all 20 Firmware CTests passed, six source repositories and 60 managed components were
  verified, and the clean ESP-IDF v5.5.4 build produced a 3,919,712 bytes gate image with 24% free.
  Its SHA-256 was
  `31a000e291428d17b746b07747ae7858e89c6ab026b7ba1c3075dff4f04dd581`. The temporary gate image
  was automatically removed and was not flashed. HW-12 remains NOT RUN; next build a retained
  candidate, obtain separate flash approval, verify its app-only write/digest/boot, then obtain a
  new explicit consent before exactly one content-suppressed retry.
- The retained app from source commit `64062cd`, including `f6f0d2d`, is
  `firmware/build-hermes-hw12-stack-64062cd/stack-chan.bin`, 3,919,712 bytes, SHA-256
  `f984c5181a48a3cf86a97f9cac59c0584d7c4eeb8a4ad8b81226c972f0cf92a6`. Its ESP32-S3 image
  checksum and validation hash are valid, with 24% app-partition headroom. Bridge, primary USB
  console, provisioning, head-motion lock and no-coredump settings passed, the partition table
  matches factory/predecessor, and the only app mapping is `0x20000 stack-chan.bin`.
- A fail-closed read-only preflight revalidated one idle serial identity, the 16 MiB factory backup
  and partition hashes, Secure Boot disabled, `SPI_BOOT_CRYPT_CNT=0`, the flashed predecessor app,
  candidate provenance/configuration, zero listeners and one exact scoped firewall rule. Separate
  explicit approval then authorized only the app write. Esptool wrote 3,919,712 bytes at `0x20000`
  in 21.0 seconds with its write hash verified; bootloader, partition table, NVS and assets were not
  written. An independent read-only digest matched the retained candidate.
- Two monitor-setup observations were rejected without treating them as Firmware failures: one had
  no deliberate reset and one had two clean boot sets from automatic plus manual reset. The accepted
  `--no-reset`/single-manual-reset window collected 16,037 bytes with exactly one ROM, reset,
  project and Firmware `1.5.1` marker and zero panic/watchdog/assert markers. Raw serial output was
  neither displayed nor retained. Postflight had one free serial port, no process/listener/capture
  temporary media, USB attached and the one scoped rule intact. No camera command was sent.
- One fresh approval was consumed by exactly one camera command in the post-stack diagnostic; the
  operator's multi-count wording was not banked as future consent, and there was no automatic retry.
  The production Control/Gateway request returned HTTP 504 `CAPTURE_TIMEOUT` after 45,091 ms at
  `device_reconnected_or_disconnected`. Aggregate evidence was `capture_completed_events=0`,
  `connection_stable=false`, zero capture/upload and failure metrics, and zero queue/device/input/
  touch events. No Firmware completion event or Gateway upload occurred.
- No image was displayed, viewed, externally processed or retained. The result exposed no image
  bytes, exact image hash or capture identifier. Cleanup left zero owned capture media and capture
  temporary directories; one serial identity was free, both WSL and Windows had no listener on
  8765/8766, USB remained attached, and exactly one approved scoped firewall rule remained.
- The 12 KiB mitigation did not resolve the physical failure because the post-stack request reached
  the same terminal stage as the prior request. This is not evidence that stack exhaustion is
  impossible and does not identify camera/driver, power/reset or HTTP behavior as the cause: neither
  failed request had a simultaneous serial trace. HW-12 remains NOT RUN. Do not repeat the unchanged
  request; first add a bounded cause-discriminating diagnostic, then obtain
  fresh explicit camera consent before any further camera command.
- The evidence update's complete host gate passed 374 tests in 28.12 seconds at 85.20% branch
  coverage; format, Ruff, strict mypy, protocol validation, secret scanning, dependency audit and
  offline doctor were also Green.
- One later fresh consent authorized the content-free serial diagnostic. It sent exactly one camera
  command with no automatic retry and returned HTTP 504 `CAPTURE_TIMEOUT` after 45,016 ms at
  `device_reconnected_or_disconnected`, with no Firmware completion, capture or upload.
- The observer read and immediately discarded 13,948 serial bytes. Aggregate evidence was
  `serial_panic_markers=2`, `serial_boot_markers=1`, `serial_reset_markers=1`,
  `serial_camera_frame_markers=0`, `serial_camera_error_markers=0`,
  `serial_brownout_markers=0`, `serial_watchdog_markers=0`, `serial_stack_markers=0`, and
  `serial_heap_markers=0`; serial disconnect/reopen counts were also zero. Two matched panic words
  may belong to one panic report, while the one boot/reset pair bounds the observed reset window.
- The `panic_observed` classification is consistent with a panic before the existing frame-copy marker,
  but content-free counters do not identify the exact panic site or select among worker startup,
  shutter/audio, camera dequeue and early frame handling. No image was displayed, viewed, externally processed or retained.
  No raw serial, image bytes, hash or identifier were exposed. Cleanup left zero owned capture media,
  one free serial identity, no WSL/Windows listener, USB attached and the one scoped rule intact.
  HW-12 remains NOT RUN; a Red stage-boundary contract must precede the smallest diagnostic or fix.
- The content-free serial evidence update's complete host gate passed 375 tests in 28.01 seconds at
  85.20% branch coverage; format, Ruff, strict mypy, protocol validation, secret scanning,
  dependency audit and offline doctor were also Green.
- One further fresh consent authorized the content-free backtrace diagnostic after its temporary
  harness passed 36 tests plus Ruff and strict mypy. It sent exactly one camera command with no
  automatic retry and returned HTTP 504 `CAPTURE_TIMEOUT` after 45,020 ms at
  `device_reconnected_or_disconnected`; Firmware completion, capture, upload, input and touch counts
  remained zero.
- The observer immediately discarded 13,726 serial bytes. Aggregate evidence was
  `serial_backtrace_addresses=9`, `serial_panic_markers=2`, `serial_boot_markers=1`,
  `serial_reset_markers=1`, `serial_camera_frame_markers=0`,
  `serial_camera_error_markers=0`, with zero brownout, watchdog, stack, heap, serial disconnect and
  reopen markers. The boot/reset pair bounds one observed reset window; two panic-word matches do
  not prove two crashes.
- Retained-ELF symbolization classified the nine bounded code addresses as
  `shutter_audio_path`. Together with the static call order and missing frame-copy marker, this
  narrows the observed panic to shutter-sound playback before camera dequeue/frame copy, but it
  does not identify the exact faulting instruction. No exact addresses, raw symbols or raw serial
  were printed, written or retained. No image was displayed, viewed, externally processed or retained.
  Cleanup left zero owned capture media, one free serial identity, no WSL/Windows listener, USB
  attached and the one scoped rule intact. At that checkpoint HW-12 remained NOT RUN pending a Red
  shutter-audio boundary contract and the smallest correction before another newly consented camera
  request.
- The content-free backtrace evidence update's complete host gate passed 376 tests in 30.29 seconds
  at 85.26% branch coverage; format, Ruff, strict mypy, protocol validation, secret scanning,
  dependency audit and offline doctor were also Green.
- A Red Firmware contract preceded the main-task shutter-audio correction in `8ad0489`: the camera
  worker now hands the shutter sound to `Application::Schedule` and no longer enters codec/timer/Ogg
  work directly. Final `./scripts/verify.sh` was Green with 377 tests passed in 30.88 seconds at 85.26% branch
  coverage, 20/20 Firmware CTests, all dependency checks and a fresh ESP-IDF build. The temporary
  3,919,968-byte gate image had SHA-256
  `feda68eb9e682cfafdb9997682addf079fda9617ee860f3fffb9a814b573ad1e` and was deleted without flash.
- The retained source-commit candidate is
  `firmware/build-hermes-hw12-shutter-8ad0489/stack-chan.bin`, 3,919,968 bytes, SHA-256
  `8b55b48a84e71820456dee68d16a2e73a7eb5ab836a8a3e8bd0638fe4686e296`. Image checksum, validation
  hash, 24% headroom, Bridge/USB/provisioning/head-lock/no-coredump configuration, factory-identical
  partition table and the `0x20000`-only app mapping passed inspection.
- Complete read-only preflight passed before separate explicit approval authorized only the app
  write. Esptool's write hash passed and an independent read-only digest matched; bootloader,
  partition, NVS and assets were not written. A physical-button monitor window was rejected after
  USB detached before boot markers. The first same-FD hard-reset window then saw one transient FreeRTOS stack-overflow
  and automatic reboot, but it did not reproduce in three consecutive clean boot windows. Each accepted
  35-second sample contained one ROM/reset/project/version marker
  and zero stack, panic, watchdog, assert, heap, brownout or disconnect markers. The transient cause
  remains unknown and no permanent fix is claimed. Raw serial was immediately discarded. There was
  no camera command during build, flash, digest or boot checks. No image was displayed, viewed, externally processed or retained.
  Postflight retained the exact scoped firewall rule and USB attachment with one free serial device,
  zero listener and zero capture media. HW-12 remains NOT RUN and the next single physical camera
  command requires fresh explicit camera consent.
- The main-task shutter-audio flash evidence host gate was Green with 378 tests passed in 31.48 seconds at 85.26%
  branch coverage; format, Ruff, strict mypy, protocol validation, secret scanning, dependency audit
  and offline doctor were Green.
- The successful post-correction HW-12 capture followed a new explicit privacy approval. Exactly one
  camera command was sent with no automatic retry; authentication and camera capability stayed
  valid, remote head capability stayed false, and the device finished in IDLE.
- The Control and storage lifecycle returned HTTP `201` / `200` / `404` for reservation, fetch and
  post-expiry fetch. It recorded `capture_completed_events=1`, `capture_completed_ok=1`,
  `capture_total=1.0`, `capture_failure_total=0.0`, `local_capture_green=true` and
  `machine_valid=true`. Completion ownership and response metadata matched without retaining the
  capture identifier.
- The 4,948-byte JPEG had valid boundaries and 320 x 240 dimensions. Temporary storage used
  directory mode `0700` and file mode `0600`; TTL purge removed the record, leaving
  `files_remaining=0`, then removed the temporary directory. No image hash was recorded.
- The authenticated connection remained stable with zero input, touch, queue and device-error
  events. The observer discarded 227 serial bytes, saw `serial_camera_frame_markers=1` and
  `serial_camera_error_markers=0`, and recorded zero panic, watchdog, stack, heap, brownout, reset and disconnect markers.
- The attended observation found that the shutter sound was not heard and no screen change was seen.
  This does not alter the valid capture/upload evidence and remains an explicit presentation
  follow-up. No image was displayed, viewed, externally processed or retained.
- Postflight had one free serial device, USB attached, no listener on 8765/8766, no owned capture
  media or temporary capture directory, and the one scoped firewall rule retained for final Goal
  cleanup. Physical CAM-001 and HW-12 were Green; at that checkpoint live Hermes `input_image`
  was still pending in CAM-002 and was completed by the later accepted vision turn.
- The HW-12 acceptance evidence host gate was Green with 379 tests passed in 31.94 seconds at 85.20%
  branch coverage; format, Ruff, strict mypy, protocol validation, secret scanning, dependency audit
  and offline doctor were Green.
- The successful HW-13 wrong-token recovery followed a nine-test temporary-harness Red→Green slice;
  Ruff, format and strict mypy were Green before either attended run. The harness first established
  authenticated IDLE, provisioned only the correct process-generated device token, and then started
  exactly one mismatched Bridge phase per explicitly initiated run.
- The accepted repeat measured `wrong_auth_failures=5.0`, `wrong_phase_registered=false`,
  `recovery_elapsed_ms=26890`, `final_state_idle=true` and `status_commands=2`. The correct phase
  re-registered the same model/Firmware with `head=false`; there was no camera, audio or actuator command.
- The content-suppressed observer discarded 1,066 serial bytes with zero boot, panic, watchdog, stack, heap, brownout and reset markers;
  serial disconnect/reopen counts were zero. There were zero input, touch, queue and device-error events.
- The first run's operator saw `Connecting Bridge` during wrong-token rejection but missed the
  recovery toast. A separately approved visual repeat was therefore required; the operator then saw
  `Bridge connected` and confirmed no contact with the device, desk or cable. The first machine run
  had also recovered cleanly, but it is not used as visual-recovery evidence.
- No token or raw serial was displayed or retained in host evidence. Postflight found a free serial
  device, USB attached, no listener on 8765/8766, no harness process, and the scoped firewall rule retained
  for final Goal cleanup. Wrong-token rejection/recovery is Green; at that checkpoint, the rest of
  HW-13 was PARTIAL.
- The HW-13 evidence host gate was Green with 380 tests passed in 32.06 seconds at 85.26% branch coverage;
  formatting, Ruff, strict mypy, protocol validation, secret scanning, dependency audit and offline
  doctor were Green.
- The successful HW-13 Hermes-stop recovery exercised local Mock Hermes through the production public HTTP/SSE client,
  together with the production Gateway, voice-turn service, failure notifier and audio streamer.
  One deliberate Mock-Hermes stop after a ready authenticated baseline produced
  `failure_error_code=HERMES_FAILED`, `failure_notification_successes=1`,
  `failure_audio_frames=0.0` and `failure_turn_released=true`, with the device returned to IDLE and
  no failure audio.
- The first approved diagnostic produced a blank Japanese toast because the Firmware toast uses
  `lv_font_montserrat_20`, then completed an inaudible 440 Hz machine-side recovery. That run was
  rejected as physical display/audio evidence. Failing tests preceded the ASCII failure-text and
  880 Hz harness corrections; the separately approved accepted run used no automatic retry.
- In the accepted run, the operator read `HERMES OFFLINE`. Recovery recorded
  `recovery_probe_ready=true`, `recovery_turn_completed=true`, `recovery_output_streams=1`,
  `recovery_audio_frames=20.0`, `recovery_elapsed_ms=35` and `recovery_device_idle=true`.
  The operator heard one 880 Hz recovery tone, saw no other screen change and reported no physical contact.
  There was no camera, microphone or actuator command and only one bounded recovery audio stream.
- The observer discarded 1,412 serial bytes with zero input, touch, queue and device-error events and
  zero boot, panic, watchdog, stack, heap, brownout and reset markers. Postflight had no listener or
  harness; Windows reported USB attached and the scoped firewall rule retained, while WSL serial enumeration was absent.
  The enumeration mismatch is retained as a prerequisite follow-up for another physical run.
- This is local contract recovery evidence, not live-provider acceptance: live HW-09 remains NOT RUN.
  The Hermes-stop slice is Green; at that checkpoint, HW-13 was PARTIAL pending TTS-stop,
  temporary Wi-Fi-loss and camera-failure evidence.
- The HW-13 Hermes-stop evidence host gate was Green with 389 tests passed in 31.83 seconds at
  85.26% branch coverage; formatting, Ruff, strict mypy, protocol validation, secret scanning,
  dependency audit and offline doctor were Green.
- The successful HW-13 TTS-stop recovery used a 13-test temporary harness whose Ruff, format and
  strict mypy checks were Green. Local Mock Hermes remained ready while a local HTTP WAV provider
  was exercised through the production TTS adapter `GenericHttpWavTtsAdapter`, Gateway,
  voice-turn service, failure notifier and audio streamer.
- The attended run established `tts_baseline_ready=true`, then used one TTS stop phase and no automatic retry.
  The provider stop yielded `failure_error_code=TTS_FAILED`, `failure_notification_successes=1`,
  `failure_audio_frames=0.0` and `failure_turn_released=true`; connection and IDLE recovery stayed Green.
- The operator read `TTS OFFLINE`, reported no abnormal screen change and confirmed no physical contact.
  A fresh provider then produced `tts_stop_phases=1`, `recovery_tts_ready=true`,
  `recovery_turn_completed=true`, `recovery_output_streams=1`, `recovery_audio_frames=20.0`,
  `recovery_elapsed_ms=35` and `recovery_device_idle=true`. The operator heard one 880 Hz recovery tone.
  There was no camera, physical microphone or actuator command and only one bounded recovery audio stream.
- The observer discarded 23,728 serial bytes with zero input, touch, queue and device-error events and
  zero boot, panic, watchdog, stack, heap, brownout and reset markers. Postflight found one free serial device,
  USB attached, no listener on 8765/8766/18767/18768, no harness and the scoped firewall rule retained.
- This was local production-adapter evidence only. At that TTS-stop checkpoint, live HW-10 was
  NOT RUN and HW-13 was PARTIAL pending temporary Wi-Fi-loss and camera-failure evidence.
- The HW-13 TTS-stop evidence host gate was Green with 390 tests passed in 33.34 seconds at
  85.26% branch coverage; formatting, Ruff, strict mypy, protocol validation, secret scanning,
  dependency audit and offline doctor were Green.
- The successful HW-13 camera-failure recovery used a 21-test temporary harness whose pytest,
  Ruff, format and strict mypy checks were Green. Fresh explicit privacy approval covered exactly
  one camera command and no host-side retry through the production `CaptureCoordinator`,
  `CaptureStore`, Device Gateway and Control API. Only the authenticated upload route was supplied
  `capture_store=None`; the harness contract proved rejection occurred before request form/body
  parsing.
- The physical command reached `serial_camera_frame_markers=1`; three bounded Firmware upload
  attempts yielded `capture_store_unavailable_responses=3`. Firmware then reported
  `capture_completed_events=1`, `capture_completed_ok=0` and `failure_event_forwarded=true`.
  Control completed after `elapsed_ms=505` with `control_status=409` and
  `control_error_code=CAPTURE_FAILED`.
- Ownership cleanup recorded `reservations=1`, `reservation_cancels=1`, `capture_total=0.0`,
  `files_remaining=0` and `temporary_directory_removed=true`. The host did not inspect the media,
  and no raw image bytes, exact image hash or capture ID were displayed or retained. Nothing was
  viewed, displayed, externally processed or stored.
- The stable authenticated connection completed `status_commands=2` and
  `final_state_idle=true`, with no audio or actuator command. The observer discarded 2,924 serial
  bytes with zero input, touch, queue and device-error events plus zero camera-error, boot, panic,
  watchdog, stack, heap, brownout and reset markers. The operator reported no shutter sound and no
  physical contact; screen presentation was not observed, so no physical display result is claimed.
- Postflight found one free serial device, USB attached, no listener on 8765/8766/18767/18768, no
  harness and the scoped firewall rule retained. The owned camera failure and IDLE recovery are
  machine Green. At that camera-failure checkpoint, HW-13 was PARTIAL solely because temporary
  Wi-Fi loss was NOT RUN.
- The HW-13 camera-failure evidence host gate was Green with 391 tests passed in 34.60 seconds at
  85.26% branch coverage; formatting, Ruff, strict mypy, protocol validation, secret scanning,
  dependency audit and offline doctor were Green.
- The successful HW-13 Wi-Fi-loss recovery used a 19-test temporary harness with pytest, Ruff,
  format and strict mypy Green. Source commit `3f3ee40` produced a 3,921,040-byte diagnostic image,
  SHA-256 `137d140de9f4279c86654949307003dfb6d216648e923cc84130057cd1acf4f3`, with the physical
  motion lock retained. It was written only at `0x20000`, and its esptool write hash, independent
  read-only digest and clean 30-second boot passed.
- The authenticated Wi-Fi-connected IDLE baseline sent `wifi_cycle_commands=1` with
  `cycle_duration_seconds=15`; the USB console recorded `cycle_start_acks=1` and
  `cycle_restart_acks=1`. The production Device Gateway recorded `websocket_disconnects=1.0`,
  `recovery_connection_replaced=true`, `recovery_elapsed_ms=11329`, `recovery_idle=true` and
  `recovery_wifi_connected=true`.
- There was no camera, audio or actuator command. The content-suppressed observer discarded
  1,286 serial bytes with zero input, touch, queue and device-error events and zero boot, panic,
  watchdog, stack, heap, brownout and reset markers. The operator saw `Connecting Bridge` and
  `Bridge connected`, reported no abnormal movement or sound and confirmed no physical contact.
- The verified 3,920,800-byte normal image from source commit `3f3ee40`, SHA-256
  `32988d0d66eea2a44e690c1b593182b411f1b1408c23eeb2d0aa59a59aca7e71`, was then written only at
  `0x20000`. Its esptool write hash, independent read-only digest and clean 30-second boot passed,
  leaving the diagnostic feature disabled. Bootloader, partition table, NVS, Wi-Fi credentials and
  assets were not rewritten. The successful HW-13 Wi-Fi-loss recovery completes HW-13 as PASS.
- The HW-13 Wi-Fi-loss evidence host gate was Green with 429 tests passed in 33.69 seconds at
  85.32% branch coverage; formatting, Ruff, strict mypy, protocol validation, secret scanning,
  dependency audit and offline doctor were Green.

## Git evidence

- Implementation HEAD used for HW-01: `7ec4114`; the baseline implementation commit is `47bd364`,
  followed by focused native-USB backup fixes `b515105` and `7ec4114`.
- The first-flash candidate adds the tested physical servo-output lock in commit `16173b3`.
- The provisioning-console boot correction is commit `fca58cf`.
- The primary interactive USB console correction is commit `ab7f1e4`.
- The ESP-IDF NVS key-limit correction is commit `a6c882e`.
- The optional command-envelope correction is commit `4abe3d9`.
- The physical K151 identity correction is commit `0a3bad2`.
- The global display-routing correction is commit `b7b2830`.
- The preinitialized toast-manager correction is commit `6faa72e`.
- The motion-free, automatically restored HW-04 visual-smoke helper is commit `a95319e`; its host
  tests and physical command/restoration path are Green, and brightness plus blue LEDs are now
  independently visible.
- The privacy-safe accepted-touch counter and shared runtime metrics wiring are commit `c94efb5`;
  their host tests are Green, but no physical counter increase has yet been observed.
- The bounded loopback GET-only reconnect transport observer is commit `4d129c7`; its host tests
  and all three bounded physical intervals are Green within their stated boundaries.
- The first global reconnect-notification correction is `e73dc30`; physical testing isolated its
  remaining launcher initialization gate. The launcher-independent correction is `7913742`, whose
  app-only write, digest, boot, transport and both visible toasts are Green.
- Background voice-turn task failure retrieval is commit `eef1390`; its physical warning was
  reproduced by a failing unit test before the minimal done-callback fix.
- Coordinated two-server SIGINT shutdown is commit `85e2c2a`; its failing unit test preceded the
  fix, and the real loopback process exited 130 without a traceback.
- Expression-time avatar initialization is commit `421457b`; its regression test, Firmware
  contract suite, 18/18 CTest, ESP-IDF build, app-only flash/digest/boot and operator-confirmed
  happy/idle path are Green.
- The no-touch input correction is commit `e19098d`: its focused tests, 19/19 CTest and fresh
  ESP-IDF build are Green. Source HEAD `fffaba3` has a retained app whose preflight, app-only write,
  independent digest and clean boot are Green. Its separately consented no-touch behavioral
  regression and deliberate-touch follow-up are physically Green; HW-02 is PASS.
- Physical playback completion is commit `5bcabc8`; its failing tests preceded tracking of the
  in-flight output frame. Cancel/new-playback isolation is source commit `e824ef4`; its failing
  tests preceded in-flight decode tracking, generation invalidation and per-stream decoder reset.
  Its retained app-only write/digest/boot and attended clean cancellation/new-turn run are Green,
  making HW-11 PASS.
- Deferred camera execution is source commit `8bfc589`; its failing tests preceded queueing in
  command handling and worker startup from the later camera update phase. Its app-only
  write/digest/boot and command-result ordering were physically verified before the later `8ad0489`
  capture completed.
- Owned failed-camera propagation and capture-package tracking are commit `517011a`; failing
  coordinator, event and ignore-contract tests preceded `camera.completed(ok=false)` →
  `CAPTURE_FAILED` wakeup and root-anchored private-output ignores.
- Scoped camera-worker stack configuration is commit `f6f0d2d`; a failing Firmware contract
  preceded its camera-only 12 KiB budget and caller-configuration restoration. The build gate is
  Green. Its retained source commit `64062cd` candidate has passed app-only flash, independent
  read-only digest and clean boot verification, but physical camera correction is not claimed.
- Bounded discovery of the actual ignored verified backup is commit `708084b`.
- Stable-idle touch re-arm is commit `9f42b92`; its failing release-bounce test preceded the
  Firmware change. Absolute monotonic audio-output pacing is commit `f73ff28`; its fake-clock test
  first reproduced cumulative WebSocket-send-delay drift. Their combined automated and physical
  HW-10 evidence is Green.
- The worktree was clean before adding these evidence-document updates.
- `git diff --check`: exit 0. Generated Firmware BIN/ELF, factory backups and user media remain
  ignored and untracked. The official MIT snapshot itself includes reviewed UI/SFX source assets
  (PNG, OGG and binary icon resources).

This report proves automated source/build behavior, HW-01, authenticated physical status HW-03,
the physical global-display/touch/brightness/LED/expression slices, bounded reconnect HW-05, fixed
Japanese physical audio output HW-06, private physical audio input HW-07 and physical cancellation/
new-turn HW-11, physical camera capture/upload HW-12, and the HW-13 wrong-token, Hermes-stop,
TTS-stop and camera-failure recovery slices. It also proves one separately approved, bounded and
physically observed K151 yaw/pitch/home sequence with clean machine evidence. It proves live HW-09
text/date/Skill Responses API behavior and latency, HW-08 live local STT behavior and latency, and
the complete physical HW-10 microphone-to-speaker turn. It also proves CAM-002 live physical
vision through one capture, live Hermes response, intelligible matching description and deletion.
HW-02, HW-04, HW-10 and HW-13 are PASS. The original no-touch
audio-input lifecycle is a safety finding whose flashed correction now passes both the attended no-
touch regression and deliberate-touch check. The latter remains HW-02 evidence; the separate
quality/stop session is HW-07 acceptance. This report must not be interpreted as reconnect latency
excluding the deliberate hold or other unmeasured physical latency. Earlier failed
HW-12 diagnostics established only their stated boundaries; the later single successful request is
the physical camera acceptance evidence.

Final Goal cleanup is complete. After evidence commit `a49adc8`, the final read-only audit recorded
`StackChanHermesBridge8765` rules=0 and all WSL Hyper-V `DefaultInboundAction=Block`. The reviewed
USB device is `Shared`, not `Attached`, with no WSL serial directory. There is no listener on
8765/8766/8642/50031; temporary TTS and SSH tunnel processes are absent, the SSH control socket is
absent, the temporary touch harness and Goal-owned `/tmp` artifacts are absent, and there is no
capture or audio media. Retained release and recovery artifacts remain ignored and untouched.
