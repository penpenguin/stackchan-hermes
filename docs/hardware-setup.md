# Hardware setup and flash safety

One StackChan/CoreS3 was identified through a stable WSL2 serial path on 2026-08-30. Its factory
boot/security/partition state and complete 16 MiB flash were read and verified for HW-01. After
explicit approval, the motion-locked custom Firmware and corrected applications were flashed and
verified. Stable boot, interactive USB provisioning, bounded NVS writes and physical Wi-Fi/IP
acquisition are Green. No erase-all or restore was performed. Authenticated Bridge hello/status/info
and restart/reconnect transport are also Green. Final Goal cleanup is complete: the one explicitly
approved narrow WSL Hyper-V firewall rule and USB attachment are removed, default inbound remains
Block, and no Bridge/TTS/Hermes listener or temporary harness remains. The authenticated display command is now
independently Green by operator visual confirmation, and HW-05 reconnect presentation is PASS after
both required toasts were observed.
For HW-04, brightness and dim-blue LEDs are physically confirmed, and
the happy expression is physically confirmed after a failing contract test exposed missing
launcher-time avatar initialization. Commit `421457b` fixed that false success; its retained
motion-locked app was written only at `0x20000`, independently digest-verified, and the operator
saw the happy eyes before an acknowledged idle restore. HW-06 audio output is PASS: the corrected,
machine-recognized fixed Japanese source completed its physical Opus playback, was properly audible,
returned to IDLE and restored volume with no underflow or device error. HW-02 boot is PASS after the
corrected touch path also passed one separately consented deliberate-touch observation.
HW-07 physical audio input is PASS. A later separately consented bounded session reconstructed and
validated both short-speech and maximum-duration WAVs, measured speech/noise without replay or
transcription, and deleted the private files immediately. The K151 yaw-pitch-home physical sequence
is Green after separately approved exact commands and clean observations. The attended candidate
was then replaced by a motion-locked normal release. The current motion-locked `d88f6df` app keeps
that diagnostic disabled and strengthens head-touch qualification to six consecutive 50 ms press
samples with three consecutive release/idle samples.
HW-08 live local faster-whisper STT is PASS. The production `small`/CPU/INT8 adapter recognized
three ephemeral Japanese patterns and returned empty for one second of silence; all temporary audio
was immediately purged. This provider check did not use the physical microphone or speaker.
HW-12 physical camera capture is PASS: one newly consented authenticated request completed JPEG
capture/upload, owned storage/fetch and TTL purge without displaying, processing or retaining the
image. The operator heard no shutter sound and saw no screen change.
CAM-002 live physical vision turn is PASS. A separately consented single capture completed one
live Hermes image request, an intelligible spoken answer that matched the observed camera scene,
and immediate owned-media deletion without displaying or retaining the image.
HW-13 wrong-token recovery is Green. A bounded attended Bridge-only test rejected the device under
one deliberately mismatched expected token, kept it unregistered with `Connecting Bridge`, then
restored the correct expected token and reached IDLE with `Bridge connected` visible. It sent no
camera, audio, motion or other actuator command, and the accepted visual repeat had no physical
contact. HW-13 Hermes-stop recovery is Green. A separately attended production-client/local-Mock
test displayed readable `HERMES OFFLINE`, released the failed turn to IDLE, recovered readiness and
played one audible 880 Hz stream without touch or another screen change. This is not live HW-09
evidence. HW-13 TTS-stop recovery is Green. A separately attended local HTTP-WAV provider stop
displayed readable `TTS OFFLINE`, released the failed turn to IDLE and completed one audible 880 Hz
stream after provider recovery without touch or abnormal screen change. This was not live HW-10
evidence at that checkpoint. HW-13 camera-failure recovery is machine Green. Under fresh explicit privacy approval,
one camera command with no host-side retry reached the physical frame path; the deliberately
unavailable Gateway capture store rejected all three bounded Firmware upload attempts before form/body
parsing. The owned failure reached Control as `CAPTURE_FAILED`, left no media and returned to IDLE.
The operator heard no shutter sound and reported no physical contact; screen presentation was not
observed, so no physical display claim is made. HW-13 Wi-Fi-loss recovery is Green. One attended,
device-local 15-second station stop produced one authenticated disconnect and a replacement
connection that returned to Wi-Fi-connected IDLE. The operator saw both `Connecting Bridge` and
`Bridge connected`, with no abnormal movement or sound and no physical contact. The diagnostic
image was then replaced app-only by the motion-locked normal release with the diagnostic disabled;
its independent digest and clean 30-second boot passed. HW-13 failure handling is PASS.
HW-11 physical cancellation is PASS. The retained source-commit `e824ef4` app resets
the Opus decoder at each new physical playback, invalidates cancellation-generation decode work
and rejects stale decoded frames. Its app-only write and independent digest verification passed.
An attended production-Gateway run then interrupted the first audible 880 Hz stream, left the
device IDLE with clean queue/device/input counters, and completed a distinct second 880 Hz turn.
The operator heard a short first beep followed by a longer second beep while touching neither the
device, desk nor cable. An isolated inaudible 440 Hz diagnostic nevertheless produced one
no-contact input lifecycle. Its content was immediately discarded and its cause remains unknown.
The prescribed separately attended bounded silent/440/880 comparison is now Green: all six phases
completed with stable state/transport and zero input, touch, queue or device-error evidence, while
the operator heard the expected two separated 880 Hz tones and touched neither the device, desk nor
cable. The earlier event is retained as historical intermittent evidence; this bounded
non-reproduction does not identify a cause or prove a permanent correction. A preceding no-touch volume comparison
played the same two-beep stream at volume 45 and 85 and restored 70. The operator confirmed that
the second volume-85 play was clearly louder than the first volume-45 play, so comparative volume is
Green. However, one unsolicited
`audio.input.start` / `audio.input.end` lifecycle occurred even though the operator touched nothing.
No input content was retained. A startup-qualified, three-sample head-touch debouncer is host/build
Green, and its explicitly approved app-only flash is digest-verified with a clean 30-second boot
observation. The subsequent 60.03-second attended no-touch regression is physically Green: the
authenticated connection stayed stable, every input/event count remained zero, and the operator
confirmed no contact. The following 51.11-second authenticated observation accepted exactly one
approximately one-second physical touch and release: one input start, 25 Opus frames, 3,617 discarded
bytes and one silence end were counted without retaining content. The operator confirmed no speech.
At that checkpoint this completed the HW-02 touch criterion only; HW-07 microphone quality and
stop-path acceptance remained NOT RUN. The later accepted HW-07 session used 68 Opus frames / 9,946
bytes for short speech and 248 Opus frames / 36,329 bytes for the silent maximum-duration path,
then left no private audio file. Neck motion was still unverified at that checkpoint; HW-12 camera
capture and the initial bounded neck movement were accepted later under distinct explicit consents.

HW-10 live physical full voice turn is PASS. On 2026-09-04, fresh consent covered one microphone
turn only. The operator touched the head once, said `今日の日付を教えて`, released it and made no
additional contact. The answer was audible and intelligible; no `Connecting Bridge` toast or
abnormal behavior appeared, and no recording was retained. Firmware commit `9f42b92` requires
stable idle before touch re-arm, while Bridge commit `f73ff28` paces output against monotonic
deadlines. The final run completed exactly one STT, Hermes and voice turn with zero connection,
disconnection, underrun, overflow, decode, authentication or timeout delta. The current device
remains motion-locked and no camera or head command was used.

## Stop-before-flash checklist

All items must be true before any write command:

- hardware is confirmed as M5Stack StackChan/CoreS3 (expected K151);
- exactly one intended serial device is identified by stable ID, not guessed from `/dev/tty*`;
- ESP-IDF v5.5.4 environment is active and the pinned baseline builds;
- full factory flash backup is exactly 16 MiB;
- backup SHA-256 is recorded and recomputes identically;
- partition table, current boot log, firmware/version identifiers, and restore command are saved;
- Secure Boot/Flash Encryption/partition risks have been checked;
- power, battery, cable, thermal state, servo mechanism, and work area are safe;
- user has explicitly approved the first flash after reviewing the artifacts.

If any item fails, stop hardware work. Continue only host/Simulator/tests/docs.

## WSL2 attachment

Follow the manual `usbipd-win` steps in `docs/operations.md`. After attaching, inspect
`/dev/serial/by-id`, `lsusb`, and candidate serial ports. Multiple candidates are a stop condition.

## Backup record

`scripts/backup-firmware.sh` defaults to dry-run, requires an explicit `/dev` port, pre-flash boot
log, firmware version and verified partition offset/size, and writes only under the explicit
destination. With `--execute-read` it reads `0x000000`–`0x1000000`, checks exactly 16,777,216
bytes, reads the partition table separately, calculates SHA-256, writes mode-0600 evidence and
records (but never executes) a restore command. Run `stackchan-bridge doctor` afterward; only a
recomputed matching 16 MiB image is reported as verified.

## Physical safety

The Hermes verification/release-candidate configuration must keep
`CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y`. This lock is enforced at the servo hardware-output
boundary: position and velocity writes plus torque enable are blocked, while torque disable
remains available. The final Firmware gate rejects a build if that setting is absent.

An attended K151 motion candidate may set `CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=n` only while
`CONFIG_STACKCHAN_HERMES_LOCAL_MOTION_LOCK=y`. The second lock is installed before motion
initialization and rejects local, avatar, IMU, BLE and app motion plus local torque enable; torque
disable remains available. Only the bounded authenticated Bridge head-command path may create a
motion target. Approval to flash such a candidate covers the app-only write and boot qualification
only. It does not authorize any physical head command, which requires a later, separate explicit
attended approval.

Start body tests with small documented ranges. Never forcibly rotate powered/unknown servos.
Stop immediately on heat, odor, swelling, unexpected noise/current, repeated servo errors, or
display/power instability. Firmware must enforce the final yaw/pitch/speed limits even when
Bridge validation is bypassed.

K151 conservative motion profile: yaw `-45..45` degrees, pitch `5..85` degrees, speed `1..30`
(default `15`), home `0/45` degrees. The profile is a conservative subset of pinned official
commit `1b5765599fba8aaad1811d9a79358ccc7051f5f3` and
[M5Stack's official StackChan servo documentation](https://docs.m5stack.com/ja/arduino/stackchan/servo),
which specifically recommends keeping the vertical servo within 5〜85° to avoid endpoint stall and
damage. Protocol speed is scaled by ten in the Firmware adapter, so the project cap `30` maps to
underlying speed `300`; the default maps to the official natural value `150`.

Bridge, MCP and Firmware host tests now reject values outside this profile without clamping.
The HAL applies the same yaw/pitch envelope to local paths and disables continuous yaw PWM for the
Hermes build. This establishes the source-backed safety profile; the separately approved attended
candidate then completed exact bounded yaw, pitch and home observations without abnormality or
contact. The current device runs the normal `head=false` verification/release configuration with
`CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y` from `d88f6df`; its Wi-Fi diagnostic is disabled.
The attended candidate used `CONFIG_STACKCHAN_HERMES_LOCAL_MOTION_LOCK=y` while globally unlocked.
Any future physical motion requires a new attended approval.
Disabling the global lock requires a separately reproducible build, complete read-only preflight,
explicit flash approval, and a second explicit approval for the smallest attended motion sequence.

Final Goal cleanup is complete. The physical device retains the verified motion-locked `d88f6df`
application, but WSL no longer owns its USB serial device and all temporary host connectivity has
been removed.
