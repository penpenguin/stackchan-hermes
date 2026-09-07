# Implementation plan

Status: the host/Simulator implementation, integrated custom Firmware build and required physical
acceptance are complete. This plan records the chronological evidence-gated path to that checkpoint.
Every future code slice continues to use the smallest Red → Green → Refactor cycle.

## Completed safe work

1. Protocol v1 schemas, examples, Pydantic models, limits and state/ownership rules are frozen and
   contract-tested.
2. The authenticated Device Gateway, Registry, Control API, audio/capture routing, health,
   readiness, metrics and optional mDNS service are implemented.
3. Opus/VAD/STT, public Hermes Responses/SSE, segmented TTS, turn cancellation and progress
   notification paths are implemented with deterministic Mock adapters.
4. The separate stdio MCP server, ten safe tools, authenticated camera lifecycle and explicit
   vision fallback are implemented.
5. The Device Simulator and Mock Hermes cover real local WebSocket/HTTP voice, capture, command,
   reconnect and injected-failure paths.
6. Service examples, privacy/debug handling, dry-run-first backup/smoke tools, operations,
   requirements and traceability are present.
7. ESP-IDF v5.5.4 commit `735507283d5b2f9fb363a1901172dbd9e847945d` is installed outside
   the repository and activates only in the Firmware shell.
8. Official `m5stack/StackChan` commit `1b5765599fba8aaad1811d9a79358ccc7051f5f3`
   is imported as a reviewed MIT vendor snapshot. Its six fetched repositories and the integrated
   set of 60 downloaded managed components plus IDF are locked; unchanged baseline evidence is
   retained separately.
9. The project-owned component and thin official HAL adapters implement authentication/hello,
   protocol guards, state/reconnect, NVS/USB provisioning, mDNS/fallback discovery, safe commands,
   touch-to-talk audio and finite camera upload. Twenty-four host C++ tests and a fresh
   Bridge-enabled ESP-IDF build pass; remote head control remains reject-all by design.

## Evidence-gated implementation record

1. **Complete (HW-01, 2026-08-30):** exactly one M5STACK-K151 serial port was identified. The
   reviewed backup flow verified the 16 MiB factory image, partition table, SHA-256, firmware
   version, boot log, per-region device digests and final whole-device digest without flashing.
2. **Complete (approved flash, 2026-08-30):** `./scripts/verify.sh` was Green with ESP-IDF v5.5.4
   active, the stable port and motion-locked image were re-reviewed, and the user explicitly
   approved the write. The first boot exposed a provisioning-console reset loop; a failing test
   preceded commit `fca58cf`, the complete gate passed again, and the corrected application was
   reflashed and verified. Two later Red→Green slices made the USB console physically interactive
   (`ab7f1e4`) and bounded every physical NVS key (`a6c882e`); each replacement app passed the
   complete gate, app-only flash and read-only digest verification.
3. **Complete (authenticated transport and HW-03, 2026-08-31):** two further Red→Green slices
   omitted absent optional command fields (`4abe3d9`) and centralized physical identity as
   `M5STACK-K151` (`0a3bad2`). The fully gated motion-locked app was flashed only at `0x20000` and
   independently digest-verified. With explicit approval, the exact named
   WSL/LocalSubnet/TCP-8765 rule was created for one bounded session. Physical hello, status/info,
   safe non-motion command acknowledgement and Bridge restart/reconnect were Green. The rule was
   removed, default inbound remained Block, process-only credentials were discarded and no
   listener remained.
4. **Complete (physical display, 2026-08-31):** commit `b7b2830` moved display text from the
   launcher-inapplicable avatar bubble to a global toast. Its first physical use exposed one
   timeout/disconnect/reconnect; a new failing lifecycle test preceded the explicit early
   toast-manager initialization in `6faa72e`. The complete gate passed, the newly approved app was
   flashed only at `0x20000` and independently digest-verified, and the operator saw
   `HERMES OK 0831` while disconnect/timeout counters remained zero. The exact temporary firewall
   rule was removed and no listener or capture remained.
5. **Complete (HW-05 reconnect, 2026-08-31):** the first approved reconnect-notification app from
   `e73dc30` was written only at `ota_0@0x20000`, independently digest-verified and observed through
   a controlled restart. Transport recovered in 9461.9 ms including the deliberate 3.0-second hold,
   but neither notification was visible. A 30-second manual global toast was visible, isolating the
   remaining defect to state presentation: launcher operation never satisfied `IsSetupUICalled()`.
   A new failing contract test preceded `7913742`, which drives the two global notifications from
   an independent dirty flag while retaining avatar-only state behind the original guard. The full
   gate passed, and after a new explicit approval the 3,918,528-byte retained app (SHA-256
   `ae5ced6a224c0991ff4d9164eec471341cb7b43404bb574762ba9aed9ba2d1a1`) was again written only at
   `0x20000` and independently verified. The final GET-only observer measured **15,697.6 ms** from
   confirmed outage to the same K151/`head=false` registration, including a deliberate 3.0-second
   Bridge-down hold. A simultaneous serial window saw no reset, panic or watchdog marker, and the
   operator saw both `Connecting Bridge` and `Bridge connected`. The former appeared below another
   toast in the stack, which remains a UX follow-up but does not invalidate the visible reconnect
   state. The exact firewall rule, Bridge/listeners, process-only token, temporary directory and USB
   attachment were removed afterward.
6. **Complete (attended evidence campaign, 2026-09-04):** the `a95319e` visual-smoke path physically
   applied/restored expression, dim LEDs and brightness with `head=false`, no motion command and
   stable metrics. On the repeated attended run, the operator saw brightness and blue LED changes
   but no happy face. Inspection proved the flashed launcher acknowledged expression while lacking
   an avatar. A failing contract test preceded `421457b`, which initializes and verifies the avatar
   before reporting expression success and clears the deferred state overwrite; focused tests,
   18/18 Firmware CTest and a fresh ESP-IDF build are Green. After explicit approval, the exact
   committed-HEAD candidate retained under `firmware/build-hermes-expression-bd49497` passed its
   one-device, backup, hash, security, motion-lock, unchanged-partition and app-only preflight. The
   previous app matched read-only; only `ota_0@0x20000` was written; write and independent digest
   checks passed; and a valid 30-second boot window had one expected reset with no panic/watchdog.
   In a separately approved bounded Bridge session, one K151 stayed connected with `head=false`,
   the operator saw the happy eyes for 20 seconds, idle restoration succeeded and all relevant
   error/touch/audio metrics stayed zero. **Complete (HW-06 audio output, 2026-09-01):** two heard
   beep controls first isolated the physical decoder/resampler/I2S/internal-speaker path. The
   original speech stimulus was then rejected because Windows PowerShell 5.1 misdecoded a BOM-less
   UTF-8 Japanese script. A Unicode-code-point-built replacement was machine-recognized as
   `こんにちは`, hash-locked, encoded into 30 Opus frames and properly audible on the K151. It
   returned to IDLE with clean counters and volume restored, so no production-code correction was
   required. The Bridge/listeners, USB attachment and temporary media were removed; the one approved
   narrow firewall rule is retained until final Goal cleanup. A later no-touch volume comparison
   played the same 25-frame beep stream at 45 and 85, restored 70 and remained transport/audio
   clean, but unexpectedly emitted one input start/end lifecycle even though the operator touched
   nothing. The Red→Green `e19098d` `HeadTouchDebouncer` correction requires a stable idle baseline
   plus three stable samples for each transition and passes 19/19 CTest plus a fresh ESP-IDF build;
   its retained source-HEAD `fffaba3` app passed read-only one-device/backup/current-app/security/
   partition/configuration preflight, was explicitly approved, written only at `0x20000`,
   independently digest-verified and clean-boot observed. The operator separately confirmed volume
   85 was clearly louder than 45, completing comparative acoustic gain. A separately consented
   attended no-touch window then stayed quiet for 60.03 seconds and is Green.
   **Complete (HW-02 deliberate touch, 2026-09-01):** the separately consented deliberate touch kept one authenticated
   connection stable for 51.11 seconds, accepted one approximately one-second touch/release, ended
   for silence and immediately discarded all 25 Opus frames / 3,617 bytes without content handling.
   The operator confirmed no speech. This completes only the HW-02 touch criterion at that
   checkpoint. **Complete (HW-07 physical audio input, 2026-09-01):** after separate explicit
   privacy consent, an initially timed-out no-result attempt was rejected and a TDD-raised attended
   timeout preceded the successful retry. Short speech reconstructed/reopened a private WAV,
   passed numeric volume/noise/VAD checks and ended for silence; an intentionally silent held-touch
   run reconstructed a second WAV and stopped at maximum duration. Both mode-0600 files were
   immediately deleted with no replay, transcription, external service, cloud service or Hermes.
   **Complete (HW-11 physical cancel, 2026-09-01):** failing playback-completion tests preceded
   `5bcabc8` and source commit `e824ef4`; the latter resets each new decoder, invalidates an
   in-flight decode generation on cancel and rejects stale playback. Its retained 3,919,184-byte
   app passed the full gates, one-device/backup/security/config preflight, explicitly approved
   app-only write, independent digest and clean boot. After two fail-closed diagnostic runs, the
   accepted attended production-Gateway run interrupted the first audible 880 Hz stream and
   completed a distinct second 880 Hz turn with zero queue/device/input errors. The operator heard
   the expected short first beep and longer second beep without touching the device, desk or cable.
   `c94efb5` provides label-free accepted-touch counting without retaining coordinates or content.
   The isolated inaudible 440 Hz diagnostic also produced one no-contact input lifecycle on the
   corrected app. Its data was immediately discarded and no cause is inferred.
   **Complete (bounded no-contact input-safety comparison, 2026-09-01):** a separately attended
   bounded silent/440/880 comparison ran six 1.2-second, 20-frame phases through the production
   Gateway. Every phase entered `SPEAKING`, returned IDLE, and retained a stable authenticated
   connection while input, touch, queue and device-error counts stayed zero. The operator heard two
   separated 880 Hz tones and confirmed touching neither the device, desk nor cable. The earlier
   event remains historical intermittent evidence; it was not reproduced in this bounded comparison
   and no cause or permanent correction is inferred.
   **Historical checkpoint (HW-12 diagnostic, 2026-09-02):** a failing Firmware test preceded `8bfc589`,
   which queues a camera request during command handling and starts its worker only in the later
   camera update phase. Its retained app was explicitly approved, written only at `0x20000`,
   independently digest-verified and clean-boot observed. One separately consented bounded request
   returned the command result but then reached `CAPTURE_TIMEOUT`, improving on the predecessor's
   `COMMAND_TIMEOUT` without proving capture/upload. A new Red coordinator/event test then showed
   that an owned `camera.completed(ok=false)` did not wake the upload waiter. Commit `517011a` maps
   that event to `CAPTURE_FAILED`, validates device ownership and tracks the capture source package.
   A second fresh consent then authorized exactly one retry. It ended after 45,227 ms at
   `device_reconnected_or_disconnected`, with `capture_completed_events=0`, no upload and no media.
   Static inspection found the capture/JPEG/HTTP path on a single 3,072-byte default-stack worker.
   A failing Firmware contract preceded `f6f0d2d`, which scopes a 12 KiB stack to only that worker;
   without a simultaneous serial trace this does not prove stack exhaustion. No image was displayed, viewed, externally processed or retained.
   Retained source commit `64062cd` candidate
   `firmware/build-hermes-hw12-stack-64062cd/stack-chan.bin`, containing `f6f0d2d`, passed complete
   preflight, an explicitly approved `0x20000`-only app write, independent read-only digest and a
   16,037 bytes single-reset boot window with zero panic/watchdog/assert markers. This is prerequisite
   evidence only. One fresh approval then authorized one post-stack diagnostic. Exactly one command
   was sent with no retry; it ended after 45,091 ms at the unchanged
   `device_reconnected_or_disconnected` stage with `capture_completed_events=0` and no upload. The
   12 KiB mitigation did not resolve the physical failure. No image was displayed, viewed, externally processed or retained.
   HW-12 remains NOT RUN. Do not repeat the unchanged request: first add a bounded
   cause-discriminating diagnostic, then obtain fresh explicit camera consent before any further
   single command; keep the privacy boundary unchanged.
   A later fresh consent authorized one content-free serial diagnostic. Its single command ended
   after 45,016 ms with `panic_observed`, one boot/reset window, no frame-copy/error marker and no
   completion/upload. This is consistent with a panic before the existing frame-copy marker, but
   the bounded result does not identify the exact panic site. No image was displayed, viewed, externally processed or retained.
   HW-12 remains NOT RUN. Add the smallest failing stage-boundary contract around worker entry,
   shutter/audio, dequeue and frame copy before implementing a diagnostic or correction; do not
   request another physical camera attempt until that source step is Green.
   A subsequent fresh consent authorized one content-free backtrace diagnostic. Its one command
   ended after 45,020 ms with no completion/upload. Retained-ELF classification of
   nine bounded code addresses was `shutter_audio_path`. The panic/reset window plus missing
   frame-copy/error markers narrows the observed failure to shutter-sound playback before camera
   dequeue/frame copy, but the bounded result does not identify the exact faulting instruction. It
   retained no exact addresses, raw symbols or raw serial. No image was displayed, viewed, externally processed or retained.
   At that checkpoint HW-12 remained NOT RUN. The next source slice required a failing shutter-audio
   boundary contract, the smallest correction and a Green Firmware gate before seeking fresh consent
   for one physical retry.
   The failing contract and main-task shutter-audio correction are complete in `8ad0489`. The
   retained candidate passed the final gate, an explicitly approved `0x20000`-only app write,
   independent read-only digest and three consecutive clean boot windows after one transient
   FreeRTOS stack-overflow did not reproduce. The transient remains unexplained and no permanent
   fix is claimed. There was no camera command during these prerequisites. No image was displayed, viewed, externally processed or retained.
   HW-12 remains NOT RUN. Obtain fresh explicit camera consent before exactly one content-suppressed
   physical retry; do not bank prior consent or retry automatically.
   **Complete (HW-12 camera, 2026-09-02):** the successful post-correction HW-12 capture used a new
   explicit privacy approval for exactly one camera command with no automatic retry. The
   authenticated capture/upload/store/fetch/TTL lifecycle finished with
   `local_capture_green=true`, `machine_valid=true` and `serial_camera_frame_markers=1`; the stable
   device returned to IDLE and all temporary media was purged. The operator reported that the
   shutter sound was not heard and no screen change was seen, so those presentation effects remain
   unconfirmed without invalidating capture/upload. No image was displayed, viewed, externally processed or retained.
   Live Hermes `input_image` remains a separate CAM-002 boundary. Any further camera command still
   requires fresh explicit privacy consent. **Complete (K151 host motion profile, 2026-09-02):**
   failing boundary/default/home tests preceded the conservative yaw `-45..45`, pitch `5..85`,
   speed `1..30` (default `15`) and home `0/45` profile. Bridge rejects unsafe K151 commands before
   send; MCP exposes the narrower inputs; Firmware revalidates them; and the official HAL uses the
   matching angle envelope with yaw PWM disabled. The normal release keeps remote head capability
   false and the servo-output lock enabled. A separately verified attended candidate was later
   app-only flashed under distinct approval with its local source lock enabled; another separate
   approval covered one bounded `yaw=5`/`pitch=45`/`speed=10` command, which was acknowledged and
   physically observed without abnormality or contact. At that checkpoint, direction-specific
   yaw/pitch and home remained later, separately approved steps.
   **Complete (K151 physical motion, 2026-09-03):** exact `yaw=10` and `pitch=40` commands later
   established positive yaw and decreasing pitch under separate approvals and clean machine/
   operator observation. The 2026-09-03 attended K151 machine-valid home then used one further
   approval and exactly one `head.home` from measured pitch 40.3 degrees, with no retry or
   additional motion. Its final yaw 0.6/pitch 44.3 readback was inside the configured 0/45
   ±2-degree neighborhood; command, connection, IDLE, input, touch, fault, reset and reconnect
   evidence was Green. The operator observed one upward movement with no abnormality or contact,
   while the bounded readback—not fine-angle visual judgment—established arrival. Thus
   machine-valid home completion is established and HW-04 is PASS. The release lock remains on,
   the attended candidate retains its local source lock, and any future motion still needs a new
   preflight and explicit approval.
   **Complete (HW-13 wrong-token recovery, 2026-09-02):** the successful HW-13 wrong-token recovery
   followed a nine-test temporary-harness Red→Green slice. The accepted attended repeat used one
   mismatch phase, recorded `wrong_auth_failures=5.0`, `wrong_phase_registered=false`,
   `recovery_elapsed_ms=26890` and `final_state_idle=true`, and sent no camera, audio or actuator command.
   The first run supplied the explicit `Connecting Bridge` observation but its recovery toast was
   missed; a separately approved repeat supplied `Bridge connected` with no device, desk or cable
   contact. No token or raw serial was displayed or retained in host evidence. Postflight kept USB
   attached and the scoped firewall rule with no listener or harness. This slice is Green; at that
   checkpoint, HW-13 was PARTIAL pending TTS-stop, temporary Wi-Fi-loss and camera-failure evidence.
   **Complete (HW-13 Hermes-stop recovery, 2026-09-02):** the successful HW-13 Hermes-stop recovery
   used local Mock Hermes through the production public HTTP/SSE client with production Gateway,
   voice-turn, notifier and audio streaming paths. One deliberate stop produced
   `failure_error_code=HERMES_FAILED`, `failure_notification_successes=1`,
   `failure_audio_frames=0.0` and `failure_turn_released=true`. The initial approved diagnostic
   rendered a blank Japanese toast because `lv_font_montserrat_20` lacks the selected glyphs, and
   its inaudible 440 Hz recovery was rejected. Failing tests preceded the ASCII notification and
   880 Hz corrections; the accepted separately approved run used no automatic retry.
   The operator read `HERMES OFFLINE`; recovery recorded `recovery_probe_ready=true`,
   `recovery_turn_completed=true`, `recovery_output_streams=1`, `recovery_audio_frames=20.0`,
   `recovery_elapsed_ms=35` and `recovery_device_idle=true`. The operator heard one 880 Hz recovery tone,
   saw no other screen change and confirmed no physical contact. There was no camera, microphone or actuator command
   and only one bounded recovery audio stream. The observer discarded 1,412 serial bytes with
   zero input, touch, queue and device-error events and zero boot, panic, watchdog, stack, heap, brownout and reset markers.
   Postflight had no listener/harness; Windows reported USB attached and the scoped firewall rule retained,
   while WSL serial enumeration was absent. This local contract evidence does not change live-provider status:
   live HW-09 remains NOT RUN. At that Hermes-stop checkpoint, HW-13 was PARTIAL pending TTS-stop,
   temporary Wi-Fi-loss and camera-failure evidence.
   **Complete (HW-13 TTS-stop recovery, 2026-09-02):** the successful HW-13 TTS-stop recovery
   used a 13-test temporary harness, local Mock Hermes and a local HTTP WAV provider through the
   production TTS adapter `GenericHttpWavTtsAdapter`. After `tts_baseline_ready=true`, the attended
   run used one TTS stop phase and no automatic retry. It produced
   `failure_error_code=TTS_FAILED`, `failure_notification_successes=1`,
   `failure_audio_frames=0.0` and `failure_turn_released=true`, while connection and IDLE recovery
   remained Green. The operator read `TTS OFFLINE`, reported no abnormal screen change and confirmed no physical contact.
   Provider recovery yielded `tts_stop_phases=1`, `recovery_tts_ready=true`,
   `recovery_turn_completed=true`, `recovery_output_streams=1`, `recovery_audio_frames=20.0`,
   `recovery_elapsed_ms=35` and `recovery_device_idle=true`. The operator heard one 880 Hz recovery tone.
   There was no camera, physical microphone or actuator command and only one bounded recovery audio stream.
   The observer discarded 23,728 serial bytes with zero input, touch, queue and device-error events and
   zero boot, panic, watchdog, stack, heap, brownout and reset markers. Postflight found one free serial device,
   USB attached, no listener on 8765/8766/18767/18768, no harness and the scoped firewall rule retained.
   This local production-adapter evidence did not establish live-provider status. At that TTS-stop
   checkpoint, live HW-10 was NOT RUN and HW-13 was PARTIAL pending temporary Wi-Fi-loss and
   camera-failure evidence.
   **Complete (HW-13 camera-failure recovery, 2026-09-02):** the successful HW-13 camera-failure recovery
   used a 21-test temporary harness with pytest, Ruff, format and strict mypy Green. Fresh explicit
   privacy approval covered exactly one camera command and no host-side retry through the production
   `CaptureCoordinator`, `CaptureStore`, Device Gateway and Control API. The Gateway alone used
   `capture_store=None`; its contract proved that authenticated uploads were rejected before request
   form/body parsing. The physical command reached `serial_camera_frame_markers=1`, and three bounded
   Firmware upload attempts produced `capture_store_unavailable_responses=3` before
   `capture_completed_events=1`, `capture_completed_ok=0` and `failure_event_forwarded=true`.
   Control returned `control_status=409` with `control_error_code=CAPTURE_FAILED` after
   `elapsed_ms=505`. Cleanup recorded `reservations=1`, `reservation_cancels=1`,
   `capture_total=0.0`, `files_remaining=0` and `temporary_directory_removed=true`.
   The device completed `status_commands=2` and `final_state_idle=true` without audio or actuator
   commands. The observer discarded 2,924 serial bytes with zero input, touch, queue and device-error
   events and zero camera-error, boot, panic, watchdog, stack, heap, brownout and reset markers.
   The host did not inspect the media, and no raw image bytes, exact image hash or capture ID were displayed or retained.
   The operator reported no shutter sound and no physical contact; screen presentation was not
   observed, so no physical display result is claimed. Postflight found one free serial device, USB
   attached, no listener on 8765/8766/18767/18768, no harness and the scoped firewall rule retained.
   The camera-failure transport/error/IDLE path is machine Green. At that camera-failure
   checkpoint, HW-13 was PARTIAL solely because temporary Wi-Fi loss was NOT RUN.
   **Complete (HW-13 Wi-Fi loss, 2026-09-03):** the successful HW-13 Wi-Fi-loss recovery used a
   19-test temporary harness with pytest, Ruff, format and strict mypy Green. Source commit
   `3f3ee40` produced a 3,921,040-byte diagnostic image, SHA-256
   `137d140de9f4279c86654949307003dfb6d216648e923cc84130057cd1acf4f3`, retaining the physical
   motion lock. It was written only at `0x20000`; the esptool write hash, independent read-only
   digest and clean 30-second boot passed. The attended run recorded `wifi_cycle_commands=1`,
   `cycle_duration_seconds=15`, `cycle_start_acks=1`, `cycle_restart_acks=1`,
   `websocket_disconnects=1.0`, `recovery_connection_replaced=true`,
   `recovery_elapsed_ms=11329`, `recovery_idle=true` and `recovery_wifi_connected=true`.
   There was no camera, audio or actuator command. The observer discarded 1,286 serial bytes with
   zero input, touch, queue and device-error events and zero boot, panic, watchdog, stack, heap,
   brownout and reset markers. The operator saw `Connecting Bridge` and `Bridge connected`,
   reported no abnormal movement or sound and confirmed no physical contact. The 3,920,800-byte
   normal image from source commit `3f3ee40`, SHA-256
   `32988d0d66eea2a44e690c1b593182b411f1b1408c23eeb2d0aa59a59aca7e71`, was then written only at
   `0x20000`; its esptool write hash, independent read-only digest and clean 30-second boot passed,
   leaving the diagnostic feature disabled. Bootloader, partition table, NVS, Wi-Fi credentials
   and assets were not rewritten. Together with the earlier failure cases, HW-13 is PASS.
7. Live Hermes v0.20 public capabilities, text/date Responses and explicit Skill use are Green.
   Live local `small`/CPU/INT8 faster-whisper is also Green for three ephemeral Japanese patterns
   and empty speech.
   **Complete (HW-10 physical full voice, 2026-09-04):** after failing tests reproduced release
   bounce and cumulative send-delay drift, `9f42b92` required stable idle before touch re-arm and
   `f73ff28` paced output against monotonic deadlines. The verified motion-locked app completed one
   freshly consented physical microphone→local STT→live Hermes→HTTP-WAV TTS→speaker turn. The
   operator heard and understood the response without a reconnect toast, abnormality or additional
   contact, and no recording was retained.
   **Complete (CAM-002 physical vision, 2026-09-04):** one separately consented capture completed
   live Hermes `input_image`, an intelligible spoken answer matching the camera scene and immediate
   deletion, with no automatic retry or retained image.
   **Complete (sustained-touch safety regression, 2026-09-04):** the CAM-002 window's one-frame
   no-contact input preceded a Red test and the `d88f6df` six-sample press threshold. Its approved
   app-only flash/digest/boot and 60-second no-touch plus one deliberate-touch check are Green.
8. **Complete (final Goal cleanup, 2026-09-04):** the applicable gates and evidence documents were
   updated, then the exact temporary Hyper-V rule, USB attachment, TTS process, Hermes tunnel,
   control socket, listeners and Goal-owned temporary artifacts were removed. Final Goal cleanup
   is complete. A firmware binary/checksum is a release artifact only after all applicable safety
   gates pass.

Do not carry a failing test into the next slice. Missing hardware never justifies weakening host
tests, while Mock/Simulator success never substitutes for Firmware build or physical evidence.
