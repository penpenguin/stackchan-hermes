# Requirements register

Status: host/Simulator and integrated custom Firmware build/host contracts are verified;
HW-10 live physical full voice turn is PASS. CAM-002 live physical vision turn is PASS.
HW-08 live local faster-whisper STT is PASS. HW-09 live Hermes Responses API is PASS.
This register records the maintained requirements and acceptance criteria.

## ARCH-001 — Three-layer ownership boundary

- **Reason:** Keep physical I/O, orchestration and agent reasoning independently maintainable.
- **Input:** StackChan hardware, Bridge services, Hermes public API.
- **Output:** Firmware ↔ Bridge ↔ Hermes paths with typed boundaries.
- **Normal:** Each layer performs only the responsibilities in `docs/architecture.md`.
- **Abnormal:** Firmware stores a Hermes key or Bridge uses Hermes internals.
- **Acceptance:** No `/api/ws`, private import, submodule coupling, or Bridge-side Memory exists.
- **Implementation:** Package layout, architecture, ADR-0001.
- **Tests:** package/secret/config contracts and repository review.
- **Status:** Layer boundaries complete; Firmware boot/provisioning/Wi-Fi and the authenticated
  physical Bridge wire boundary are exercised. The live Hermes public API and local STT boundaries
  are Green; the live physical TTS/full-voice and image-interpretation paths are Green.

## PROTO-001 — Versioned, bounded Protocol v1

- **Reason:** Malformed device traffic must not corrupt state or exhaust memory.
- **Input:** WebSocket text JSON and directional raw Opus binary packets.
- **Output:** Strict envelopes, typed control/event/command families and explicit errors.
- **Normal:** Schema and Pydantic accept every valid example.
- **Abnormal:** Oversize/deep/invalid/version-mismatched input closes with a typed reason.
- **Acceptance:** 11 valid/8 invalid examples agree; all sizes/ranges are bounded.
- **Implementation:** `protocol/*.schema.json`, `protocol/models.py`, protocol/state docs.
- **Tests:** `test_protocol_contract.py`, `test_protocol_models.py`, Firmware protocol/guard tests.
- **Status:** Bridge/Schema/Firmware host parity Green; physical authenticated hello/status/info
  and reconnect transport are Green.

## PROTO-002 — Authentication, ownership, heartbeat and idempotency

- **Reason:** Only one authenticated current connection may own device state and streams.
- **Input:** Bearer token, device header, hello, message/request/turn/stream IDs.
- **Output:** hello_ack, newer-connection-wins, pong, duplicate suppression and cleanup.
- **Normal:** One connection owns at most one input/output stream and correlated commands.
- **Abnormal:** Wrong identity/token/version, stale result, duplicate or orphan binary is rejected.
- **Acceptance:** Real WebSocket handshake/command and duplicate/reconnect tests pass.
- **Implementation:** Device Gateway/Registry, Simulator, Uvicorn ping configuration and Firmware
  session/transport/reconnect component.
- **Tests:** Gateway/handshake/integration plus Firmware protocol/session/reconnect tests.
- **Status:** Both peers host-tested; physical authentication, hello, command/result ownership and
  restart/reconnect transport are Green. A bounded physical wrong-token phase was rejected without
  registration, then the same device recovered to authenticated IDLE after the correct Bridge
  returned; both connecting and connected presentation were observed.

## FW-001 — Pinned official baseline

- **Reason:** Preserve official CoreS3 support and minimize unsafe board divergence.
- **Input:** `m5stack/StackChan` pin, license, ESP-IDF v5.5.4.
- **Output:** Reproducible unchanged baseline plus isolated component/HAL integration.
- **Normal:** Exact pin builds before custom code.
- **Abnormal:** SHA/license/toolchain drift stops import/build.
- **Acceptance:** notices preserved and `idf.py build` exits 0 without skip.
- **Implementation:** reviewed vendor snapshot, MIT notice, `upstream-lock.json`, dependency
  verifier, `firmware/UPSTREAM.md` and ADR-0006.
- **Tests:** provenance/contract tests, 24 host C++ tests, unchanged baseline and integrated
  Bridge-enabled ESP-IDF builds.
- **Status:** Baseline/integrated build and stable physical custom boot Green.

## FW-002 — Hardware abstraction, settings, state and local presentation

- **Reason:** Board I/O and autonomous UI must remain safe and network-independent.
- **Input:** Official BSP/HAL, NVS settings, Wi-Fi/mDNS/fixed URL, state events.
- **Output:** validated runtime provisioning and BOOTING…UPDATING state machine.
- **Normal:** existing BSP controls LCD/touch/camera/audio/servo/LED; UI follows local state.
- **Abnormal:** missing config/hardware enters ERROR and rejects body/media commands.
- **Acceptance:** one runtime provisioning path plus FW transition/settings tests.
- **Implementation:** official BSP/HAL, `stackchan_bridge_client`, `stackchan_bridge_service`,
  display/WebSocket/mDNS adapters and USB serial provisioning.
- **Tests:** Firmware contract plus settings/state/discovery/provisioning/session C++ tests.
- **Status:** Implemented and ESP-IDF-build Green; primary USB provisioning input, all bounded NVS
  writes, physical Wi-Fi/IP acquisition and authenticated Bridge WebSocket are Green. The global
  display notification was acknowledged without disconnect and independently seen on the physical
  LCD. Brightness and dim-blue LED effects are also physically visible. The launcher's expression
  false-success was fixed in `421457b`, flashed app-only, digest-verified and physically confirmed.
  A later no-touch volume comparison unexpectedly produced one input start/end lifecycle. A tested
  startup guard and three-sample `HeadTouchDebouncer` in `e19098d` now suppress unqualified
  transitions. The retained `fffaba3` app is flashed/digest/boot verified.
  The no-touch false activation correction is physically Green after a quiet attended 60.03-second regression;
  a separately consented 51.11-second observation then accepted exactly one approximately one-
  second touch/release, ended for silence and stayed connection-stable. This completes the FW-002/
  HW-02 touch behavior without claiming HW-07 microphone quality or stop-path acceptance.

## FW-003 — Physical safety, bounded audio and camera

- **Reason:** Untrusted commands/media must never create hazardous movement or memory growth.
- **Input:** validated commands, Opus streams, capture requests.
- **Output:** board-specific reject-not-clamp motion, bounded PSRAM queues and JPEG upload.
- **Normal:** task-separated audio, preroll/gain/cancel, one capture with finite retries.
- **Abnormal:** unknown board limits reject all motion; overflow/busy/errors are reported.
- **Acceptance:** servo/queue/camera/audio FW tests and physical evidence pass.
- **Implementation:** bounded Firmware audio input/output and gain, command executor, finite camera
  capture/upload, official HAL adapters, board-specific reject-not-clamp motion validation and a
  release-candidate servo-output lock for position, velocity and torque enable. K151 conservative
  motion profile: yaw `-45..45` degrees, pitch `5..85` degrees, speed `1..30` (default `15`), home
  `0/45` degrees.
- **Tests:** Firmware command/audio/camera/safety C++ tests, servo-output gate tests and Bridge
  contract parity.
- **Status:** Host/build and safe physical non-motion command acknowledgement Green; brightness,
  LED, corrected happy-expression and fixed Japanese output are physically Green. Identical low/high
  beep streams were both audible and restored safely; the operator confirmed volume 85 was clearly
  louder than 45, so comparative acoustic gain is Green. One newly consented authenticated physical
  capture completed JPEG upload, validation, fetch and TTL purge without retained media, making the
  physical camera lifecycle Green. The operator heard no shutter sound and saw no screen change,
  confirming that no unwanted presentation effect occurred. The source-backed K151 profile is host Green and
  enforced by Bridge, MCP, Firmware command handling and the HAL envelope. The normal release motion
  lock remains enabled by default. The separately approved, app-only-flashed attended candidate
  kept its local-command lock on. Exact `yaw=10` and `pitch=40` commands established positive-yaw
  and decreasing-pitch direction; a final home-only run moved once from measured pitch 40.3 to
  44.3 degrees inside the configured 0/45 tolerance. All three attended checks had clean bounded
  machine evidence and no abnormality or contact. The K151 yaw-pitch-home physical sequence is
  Green and HW-04 is PASS. The current device contains the motion-locked `d88f6df` release with its
  Wi-Fi diagnostic disabled, stable-idle touch re-arm and sustained six-sample press filter.

## FW-004 — Reconnect and flash safety

- **Reason:** Service loss must recover without reboot; flash must remain recoverable.
- **Input:** Wi-Fi/socket failures, unique serial identity, factory image and partition data.
- **Output:** 1/2/4/8/16/30 backoff, stale-task destruction, verified backup before flash.
- **Normal:** stable connection resets backoff; full backup and SHA precede any write.
- **Abnormal:** ambiguous port, bad size/SHA, security/partition risk stops flash.
- **Acceptance:** FW reconnect tests plus HW-01/HW-05 pass before a flash claim.
- **Implementation:** Firmware reconnect/session state, stale-socket replacement,
  launcher-independent global notifications, backup script, GET-only reconnect observer and
  hardware setup/ADR.
- **Tests:** Firmware reconnect/session tests, Simulator backoff, reconnect-observer and backup
  contracts; HW-01 digest evidence.
- **Status:** Firmware/host safety, HW-01 and HW-05 Green. The final physical restart recovered in
  15,697.6 ms including a deliberate 3.0-second down hold; simultaneous serial evidence contained
  no reset/panic/watchdog marker and both reconnect toasts were independently visible.

## BR-001 — CLI and validated configuration

- **Reason:** Operators need reproducible, secret-safe control without global installation.
- **Input:** CLI > environment > TOML > safe defaults.
- **Output:** serve/doctor/devices/token/captures/MCP/Simulator entrypoints.
- **Normal:** valid config selects adapters/binds/limits and named secret variables.
- **Abnormal:** unsafe endpoint, management bind, missing secret or invalid bounds fail fast.
- **Acceptance:** all required commands and precedence/config-example tests pass.
- **Implementation:** `cli.py`, `config.py`, `pyproject.toml`, examples.
- **Tests:** `test_config*.py`, `test_package_contract.py`.
- **Status:** Complete.

## BR-002 — Authenticated Device Gateway and Registry

- **Reason:** Device identity/capability and async command ownership must be deterministic.
- **Input:** authenticated hello, control/events/binary frames, command results, uploads.
- **Output:** live registry, typed capability/disconnect/timeout errors and routing.
- **Normal:** command/capture/audio/event reaches only its current owner.
- **Abnormal:** duplicate connection, stale result, limit/rate/timeout or absent capability fails.
- **Acceptance:** gateway unit and real Uvicorn Simulator integrations pass.
- **Implementation:** `device_gateway/application.py`, capture/audio/event handlers.
- **Tests:** gateway, upload, audio, command and bridge integration suites.
- **Status:** Complete for host/Simulator and physical authenticated hello/status/info/reconnect.

## BR-003 — Loopback Control, health, metrics and mDNS

- **Reason:** MCP/operations need a local surface while only device traffic reaches LAN.
- **Input:** Registry, dependency checks, capture/turn services and service metadata.
- **Output:** live/ready, devices/commands/captures/vision/reset, metrics and optional discovery.
- **Normal:** readiness checks dependencies but not device presence; fixed URL works without mDNS.
- **Abnormal:** non-loopback control bind or missing required dependency is unready.
- **Acceptance:** endpoint/error/readiness/metrics/mDNS tests pass.
- **Implementation:** control app, runtime, metrics, discovery.
- **Tests:** `test_control_api.py`, `test_runtime.py`, `test_mdns.py`.
- **Status:** Complete for loopback and physical device liveness/commands/metrics. Live local STT,
  Hermes Responses/SSE and HTTP-WAV TTS dependencies are Green through the physical voice path.

## AUDIO-001 — Opus, normalization, VAD and private debug storage

- **Reason:** Voice input/output must be bounded, cancellable and private.
- **Input:** 16 kHz mono Opus/PCM, configurable RMS/noise thresholds.
- **Output:** resilient decode, deterministic utterance, ordered Opus output, optional TTL WAV.
- **Normal:** preroll/hysteresis/min/max rules select one utterance.
- **Abnormal:** corrupt packet recovers with fresh decoder; limits cancel; noise/empty fails safely.
- **Acceptance:** codec/input/output/VAD/debug-store and full Simulator voice tests pass.
- **Implementation:** `audio/*`, runtime audio settings.
- **Tests:** `test_audio_*.py`, `test_vad.py`, `test_debug_audio_store.py`.
- **Status:** Complete for host/Simulator, physical audio input and output, and physical
  cancel-before-new-turn. The separately
  consented K151 capture reconstructed private WAVs, measured short-speech volume/noise/VAD and
  verified an independent maximum-duration stop. The cancellation-corrected app physically stopped
  one audible stream and completed a distinct clean new stream. Live local STT and the full
  provider-backed physical voice path are Green.

## AUDIO-002 — Provider-neutral STT

- **Reason:** Recognition must be replaceable and never send empty text to Hermes.
- **Input:** bounded PCM/WAV and cancellation/timeout.
- **Output:** typed text/language/confidence/duration/metadata.
- **Normal:** Mock, generic HTTP and faster-whisper adapters return normalized results.
- **Abnormal:** timeout/provider/empty maps to safe UI and releases the turn.
- **Acceptance:** adapters, lazy off-thread load, timeout and failure-notification tests pass.
- **Implementation:** `stt/*`, doctor cache detection, turn service.
- **Tests:** `test_stt.py`, voice/notification/package tests.
- **Status:** Complete. HW-08 live local faster-whisper STT is PASS: the production `small`/CPU/INT8
  adapter recognized three ephemeral Japanese patterns in 3,689/2,150/2,238 ms and returned an
  empty result for one second of silence in 10,961 ms, with no audio retained.

## AUDIO-003 — Segmented, ordered TTS

- **Reason:** Japanese speech should start early without reordering or stale playback.
- **Input:** bounded speakable segments and provider timeout/cancellation.
- **Output:** normalized 16 kHz PCM, Opus streams in source order and timing metrics.
- **Normal:** Mock, generic HTTP WAV and VOICEVOX synthesize concurrently/play sequentially.
- **Abnormal:** timeout/error/cancel discards stale work; abort/play-completed policy is explicit.
- **Acceptance:** adapter, ordering, policy, cancellation and timing tests pass.
- **Implementation:** `tts/*`, audio output, SpeechSegmenter.
- **Tests:** `test_tts*.py`, voice/Simulator flow.
- **Status:** Complete for host/Simulator, intelligible fixed-Japanese physical playback,
  physical cancellation/new-turn isolation and the live HTTP-WAV provider path used by HW-10.

## HERMES-001 — Public Responses API capability/request boundary

- **Reason:** Avoid internal Hermes coupling while retaining Memory/Skills/MCP ownership.
- **Input:** Bearer public health/capabilities and streamed `/v1/responses`.
- **Output:** model selection, named device conversation, stable session key and inline image.
- **Normal:** required core/discovery surfaces make readiness true.
- **Abnormal:** missing model/capability/path keeps readiness false; no private fallback occurs.
- **Acceptance:** request/header/body/probe/text/vision tests pass against Mock Hermes; required
  text and Skill turns pass against the live public API.
- **Implementation:** `hermes/client.py`, runtime readiness, Mock Hermes.
- **Tests:** `test_hermes_client.py`, `test_mock_hermes.py`, runtime tests.
- **Status:** Host and live text/Skill complete. Hermes v0.20.0 nested capabilities are normalized
  without weakening legacy checks; authenticated readiness, three Responses/SSE text turns and the
  CAM-002 live `input_image` turn are Green.

## HERMES-002 — SSE, segmentation, reset and typed failures

- **Reason:** Streaming/tool lifecycle must be safe, speakable and diagnosable.
- **Input:** bounded SSE created/delta/item-added/item-done/completed/error/close.
- **Output:** Japanese segments, thinking→idle notifications, no duplicate tool execution.
- **Normal:** first complete sentence starts TTS; conversation reset preserves Memory session key.
- **Abnormal:** 401/404/429/5xx/timeout/transport/malformed/early-close remain distinct.
- **Acceptance:** parser, segmenter, error matrix, reset and progress tests pass.
- **Implementation:** Hermes client/segmenter, voice/vision services and notifications.
- **Tests:** Hermes, segmenter, voice, vision and notification suites.
- **Status:** Complete for deterministic host behavior and live text/Skill streaming. Measured live
  completion latencies were 2,721 ms, 5,665 ms and 8,590 ms.

## MCP-001 — Separate safe stdio server and twelve tools

- **Reason:** Hermes controls intentional actions without direct device/network coupling.
- **Input:** validated MCP arguments and loopback Control API responses.
- **Output:** status/photo/head/home/expression/LED/text/volume/cancel/touch/speak/speech-status tools.
- **Normal:** tools return bounded typed results/ImageContent where supported.
- **Abnormal:** disconnected/capability/invalid response returns safe ToolError, never crashes.
- **Acceptance:** twelve tools, stdio/no-stdout, loopback URL and photo fallback tests pass.
  Direct speech accepts up to 1,000 characters asynchronously, rejects busy devices, and exposes
  bounded status history with cancellation, failure, reconnection and shutdown coverage.
- **Implementation:** `mcp_server/*`, `examples/hermes-config.yaml`.
- **Tests:** `test_mcp_server.py`, `test_mcp_control_client.py`, speech service/API/integration and package tests.
- **Status:** Complete for the project stdio server. Live Hermes Skill discovery and explicit
  `skill_view` use are Green; live ingestion of this project's MCP server remains unverified.

## CAM-001 — Authenticated capture lifecycle and security

- **Reason:** Device images are private untrusted media.
- **Input:** Bridge UUID reservation and authenticated bounded multipart JPEG.
- **Output:** owned mode-0600 record, dimensions/SHA/TTL and generated path.
- **Normal:** one device uploads its reservation and later fetch/delete/purge succeeds.
- **Abnormal:** wrong auth/owner/MIME/magic/size/dimensions/path/collision/rate is rejected.
- **Acceptance:** store/upload/coordinator/Control and real Simulator capture tests pass.
- **Implementation:** captures store/coordinator, Gateway upload, Control API.
- **Tests:** capture suites and `test_bridge_integration.py`.
- **Status:** Complete for host/Simulator and the physical camera lifecycle. One explicit-consent
  physical request completed authenticated JPEG upload, owned storage, fetch and TTL purge with no
  retained media. Shutter sound and screen feedback were not observed.

## CAM-002 — Explicit vision and MCP fallback

- **Reason:** Vision must not depend solely on MCP ImageContent support.
- **Input:** explicit question/quality plus owned JPEG.
- **Output:** Responses `input_image`, spoken answer, ImageContent/local URL/vision fallback.
- **Normal:** capture→inline image→SSE→TTS completes one owned vision turn.
- **Abnormal:** busy/disconnect/upload/Hermes/TTS/image-fetch maps to typed safe error.
- **Acceptance:** Vision service/API/MCP fallback tests pass.
- **Implementation:** `turns/vision.py`, Hermes client, Control/MCP.
- **Tests:** `test_vision_turn.py`, Control/MCP/Hermes tests.
- **Status:** CAM-002 live physical vision turn is PASS. One freshly consented physical capture
  completed inline live Hermes `input_image`, an intelligible spoken Japanese response matching
  the camera scene and immediate owned-media deletion. There was no automatic retry or retained
  image. Physical capture remains Green under CAM-001.

## SEC-001 — Network and secret boundaries

- **Reason:** Management credentials/media must not leave intended trust zones.
- **Input:** bind settings, API/device keys, configs, logs/reports.
- **Output:** LAN device-only surfaces, loopback management/Hermes, redacted artifacts.
- **Normal:** separate secrets enter through named environment variables.
- **Abnormal:** URL credentials, non-loopback management, wildcard/private API or leaked secret fails.
- **Acceptance:** config/auth/log/report/repository secret tests and scan pass.
- **Implementation:** config validators, token module, logging/debug report, ignores.
- **Tests:** security/config/log/debug-report/secret suites.
- **Status:** Complete for LAN v1, including physical wrong-token rejection and authenticated
  recovery without retaining the compared token in host evidence; unencrypted `ws://` risk remains
  documented.

## SEC-002 — Resource, rate and physical capability limits

- **Reason:** LAN peers/providers must not exhaust Bridge or bypass device abilities.
- **Input:** JSON/audio/image/connection/request/capture/timeout settings and hello capabilities.
- **Output:** bounded processing and pre-send capability rejection.
- **Normal:** configured traffic and advertised commands proceed.
- **Abnormal:** burst, oversize, too many connections/pending commands or missing hardware fails.
- **Acceptance:** limit/rate/capability matrices pass and config exposes every bound.
- **Implementation:** protocol/config, rate limiter, Gateway/Registry, stores/adapters.
- **Tests:** protocol/gateway/capture/control/config tests.
- **Status:** Bridge and Firmware host enforcement Green, including K151 profile parity. The isolated
  attended candidate was app-only flashed; separately approved exact yaw, pitch and home commands
  completed with clean fail-closed guards. The candidate was then replaced by the motion-locked
  normal release. Any future physical motion remains a new attended approval boundary.

## OBS-001 — Safe logs, metrics and doctor

- **Reason:** Async failures require correlation without exposing private content.
- **Input:** lifecycle events, IDs, durations, dependency/config state.
- **Output:** allow-listed JSON logs, required Prometheus metrics and online/offline diagnosis.
- **Normal:** device/touch/turn/STT/Hermes/TTS/capture metrics and readiness are machine-readable.
- **Abnormal:** provider bodies/keys/transcripts/media never enter normal diagnostics.
- **Acceptance:** structured log, metrics, doctor normal/partial/backup/cache tests pass.
- **Implementation:** observability, touch events, coordinator/services, doctor/CLI.
- **Tests:** logging/control/runtime/touch/package/TTS tests.
- **Status:** Complete; accepted live text, voice and vision latency evidence is recorded in
  `verification-report.md`.

## OPS-001 — Device Simulator and Mock Hermes

- **Reason:** CI must reproduce major paths without hardware or live Hermes.
- **Input:** runtime token, generated WAV/JPEG, scenarios/events/fault options.
- **Output:** handshake/command/capture/full voice, events, reconnect and public mock SSE.
- **Normal:** real Uvicorn round trips complete and output WAV is reconstructed.
- **Abnormal:** auth/version/delay/disconnect/malformed/duplicate/provider faults are selectable.
- **Acceptance:** dedicated Simulator E2E and mock/fault suites pass with no tracked media.
- **Implementation:** `simulator/*`, `run-simulator-e2e.sh`.
- **Tests:** all `simulator/tests` plus Gateway fault tests.
- **Status:** Complete.

## OPS-002 — Safe service, backup, report and update operations

- **Reason:** Long-running host service and recovery artifacts need bounded repeatable procedures.
- **Input:** external env/config, service manager, explicit serial/evidence paths.
- **Output:** restart backoff, token/device steps, dry-run backup, redacted report, rollback guide.
- **Normal:** Hermes may start later and readiness recovers; services restart abnormal exits.
- **Abnormal:** missing backup evidence/port/tool/config stops action without mutation.
- **Acceptance:** script/service contracts, dry run and docs review pass.
- **Implementation:** scripts, launchd/systemd examples, operations/hardware docs.
- **Tests:** `test_scripts_contract.py`, `test_debug_report.py`, doctor backup test.
- **Status:** Host complete; approved custom flash and corrected application reflash verified;
  erase-all and restore NOT RUN.

## TEST-001 — Strict TDD and host quality gate

- **Reason:** Async cross-device regressions require small evidence-backed changes.
- **Input:** every behavior/bug change.
- **Output:** Red→Green→Refactor tests, formatting, lint, typing, coverage and audits.
- **Normal:** `verify-host.sh` propagates failures and reaches precise coverage ≥85.00%.
- **Abnormal:** failed test/coverage/scan/audit exits nonzero; no silent optional skip claim.
- **Acceptance:** current host gate exits 0 with concrete test/coverage evidence.
- **Implementation:** AGENTS, pyproject, verify scripts, CI host job.
- **Tests:** script/CI/package contracts and full suite.
- **Status:** Complete for host.

## TEST-002 — Integration, fault and race coverage

- **Reason:** Unit success alone does not prove transport/ownership behavior.
- **Input:** real local sockets/ASGI, concurrent tasks and injected failures.
- **Output:** voice/capture/command/MCP/cancel/reconnect results without stale state.
- **Normal:** Simulator↔Bridge↔Mock providers complete major paths.
- **Abnormal:** timeout/disconnect/corrupt/duplicate/stale/cancel races fail safely.
- **Acceptance:** integration/fault suites pass with actual Uvicorn where required.
- **Implementation:** Simulator, runtime and test harnesses.
- **Tests:** Simulator integration/voice/reconnect plus Bridge fault suites.
- **Status:** Complete for host surfaces.

## TEST-003 — Firmware and hardware acceptance

- **Reason:** Physical and toolchain behavior cannot be inferred from Python tests.
- **Input:** imported pin, ESP-IDF, unique K151, verified backup, HW-01…HW-13.
- **Output:** successful build/size/checksum and recorded physical results/latency.
- **Normal:** `verify-firmware.sh` and all safe applicable hardware scenarios pass.
- **Abnormal:** missing dependency/evidence is explicit and stops flash/testing.
- **Acceptance:** final `verify.sh` exits 0 without skip and hardware report contains evidence.
- **Implementation:** fresh Bridge-enabled motion-locked build gate, reviewed source/dependency
  lock, 22 C++ targets, fail-closed contract, report and hardware checklists.
- **Tests:** baseline/integrated ESP-IDF builds and Firmware host tests Green;
  HW-01/HW-02/HW-03/HW-04/HW-05/HW-06/HW-07/HW-08/HW-09/HW-10/HW-11/HW-12/HW-13 PASS.
- **Status:** Automated Firmware gate, verified backup/app, physical authenticated status and
  display plus brightness, LED, corrected expression, reconnect transport/presentation, fixed
  Japanese audio output and private physical audio input are Green. The expression correction was
  written app-only, independently digest-verified and operator-confirmed. The no-touch input correction is build Green and its
  app-only flash/digest/boot plus physical no-touch and deliberate-touch behavioral checks pass.
  HW-02 is PASS. A distinct consented session reconstructed/validated short and maximum-duration
  WAVs, completed numeric quality/VAD/stop checks, deleted both immediately and makes HW-07 PASS.
  Commit `e824ef4` isolates decoder generations across cancel/new playback; its 20/20 CTest,
  app-only flash/digest/boot and attended clean short-then-long sound observation make HW-11 PASS.
  One isolated, physically inaudible 440 Hz probe produced a no-contact input lifecycle whose
  content was discarded. Its prescribed separately attended bounded silent/440/880 comparison is
  Green: six phases completed with zero input/touch/error evidence and the operator confirmed two
  separated 880 Hz tones with no contact. The original event remains historical intermittent
  evidence and was not reproduced; no cause or permanent correction is inferred.
  A later freshly consented single camera command on the main-task shutter-audio candidate completed
  authenticated capture/upload, valid 320×240 JPEG storage/fetch and TTL purge with stable transport
  and no retained media, making HW-12 PASS. The absent shutter sound and screen change remain
  presentation observations. CAM-002 live physical vision turn is PASS in the later separately
  consented capture→Hermes→speech lifecycle.
  The 2026-09-03 attended K151 machine-valid home completed the previously pending HW-04 motion
  sequence. A separately approved home-only run sent exactly one `head.home` from measured pitch
  40.3 degrees, reached yaw 0.6/pitch 44.3 inside the configured 0/45 ±2-degree neighborhood, and
  had clean command, connection, IDLE, input, touch, fault, reset and reconnect evidence. The
  operator observed one upward movement with no abnormality or contact but did not independently
  resolve the fine final angle by eye; the bounded readback supplies that evidence. Thus
  machine-valid home completion is established, and the prior yaw, pitch, expression, LED,
  brightness and volume evidence makes HW-04 PASS. Historical failed-closed attempts remain
  recorded.
  HW-13 PASS: a separately attended wrong-token mismatch was rejected without registration,
  and a correct Bridge restored authenticated IDLE. The operator saw `Connecting Bridge` and, on an
  explicitly approved visual repeat, `Bridge connected` without physical contact. A later local
  Mock-Hermes stop through the production public HTTP/SSE client displayed readable
  `HERMES OFFLINE`, released the failed turn, recovered readiness and completed one audible 880 Hz
  stream without contact. A later local HTTP-WAV provider stop through the production TTS adapter
  displayed readable `TTS OFFLINE`, released the failed turn and completed one audible 880 Hz
  stream after provider recovery without contact. A freshly approved single physical camera command
  then exercised the unavailable-store failure path: the owned `camera.completed(ok=false)` became
  Control `CAPTURE_FAILED`, left no media and returned the device to IDLE. The operator reported no
  shutter sound and no contact, while the screen was not observed and therefore supplies no display
  claim. A final attended device-local 15-second Wi-Fi loss then produced exactly one authenticated
  disconnect, a replacement connection after 11,329 ms and Wi-Fi-connected IDLE recovery. The
  operator saw both `Connecting Bridge` and `Bridge connected` without abnormal movement, sound or
  contact. The one-shot diagnostic image was replaced app-only by the independently verified,
  motion-locked normal release with the diagnostic disabled. This completes HW-13.
  HW-10 live physical full voice turn is PASS. A single freshly consented touch and utterance
  completed one microphone→local STT→live Hermes→HTTP-WAV TTS→speaker turn. The operator heard and
  understood the answer with no reconnect toast, abnormality or additional contact; no recording
  was retained. Stable-idle touch re-arm and monotonic-deadline output pacing removed the preceding
  duplicate-turn and underrun findings.
  The CAM-002 window also exposed one no-contact input frame without an STT request. The tested
  `d88f6df` follow-up now requires six consecutive 50 ms press samples and three consecutive
  release/idle samples. Its app-only flash/digest/boot and a 60.000-second no-touch plus single
  deliberate-touch physical regression are Green. Final Goal cleanup is complete: the scoped
  firewall rule, USB attachment and bounded helper connectivity were removed after acceptance.

## DOC-001 — Documentation, ADR and end-to-end traceability

- **Reason:** Requirements, decisions, verification and known limits must remain auditable.
- **Input:** [Requirements register](requirements.md), implementation, test/gate output and
  external evidence.
- **Output:** architecture/protocol/state/security/operations/hardware/progress/report/traceability.
- **Normal:** every registered requirement maps to implementation/test/result.
- **Abnormal:** unavailable evidence is marked NOT RUN/blocked, never implied PASS.
- **Acceptance:** documents agree with current code/Git/toolchain/hardware state.
- **Implementation:** `docs/*`, ADR-0001…0006, notices and README.
- **Tests:** config/script/package contracts plus manual cross-document review.
- **Status:** Final Goal cleanup is complete; current documents agree with the completed automated
  and physical evidence and the cleaned host/network boundary.
