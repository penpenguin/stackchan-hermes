# Hardware test report

Status: **SAFE CHECKPOINT — HW-01 through HW-13 PASS; reconnect, brightness, LED, expression,
touch, physical full voice, cancel-before-new-turn, physical camera lifecycle, live Hermes
text/Skill, wrong-token recovery plus local-public-contract Hermes-stop, HTTP-WAV TTS-stop and
Wi-Fi-loss recovery confirmed; CAM-002 live physical vision turn is PASS; final cleanup complete**

| Field | Value |
| --- | --- |
| Date | 2026-09-01 (Asia/Tokyo) |
| Latest evidence date | 2026-09-04 (Asia/Tokyo) |
| Hardware model | M5Stack StackChan/CoreS3; ESP32-S3 QFN56 rev 0.2, 16 MiB QIO flash, 8 MiB PSRAM |
| Serial identity | Exactly one Espressif USB Serial/JTAG device reviewed through a stable WSL `/dev/serial/by-id` path; the raw identifier remains only in local private evidence |
| Factory Firmware | Project `stack-chan`, version `1.4.4`, ESP-IDF v5.5.4; active app was `ota_1` |
| Security state | Secure Boot disabled; Flash Encryption disabled; `SPI_BOOT_CRYPT_CNT=0` |
| Firmware source | StackChan 1.5.1 commit `1b5765599fba8aaad1811d9a79358ccc7051f5f3` plus current custom component/HAL overlay |
| Current flashed image | `firmware/build-hermes-touch-filter-d88f6df/stack-chan.bin`; source commit `d88f6df`; 3,920,848 bytes; SHA-256 `32ec714f11a7c906e6ff73f3c7813f3ed5a0fb06328df1b6db0acba1ae54d881`; motion lock enabled and attended Wi-Fi diagnostic disabled; app-only write, independent read-only digest and clean boot verified before the sustained-touch regression |
| Previous normal image | `firmware/build-hermes-normal-3f3ee40/stack-chan.bin`; source commit `3f3ee40`; 3,920,800 bytes; SHA-256 `32988d0d66eea2a44e690c1b593182b411f1b1408c23eeb2d0aa59a59aca7e71`; app-only restore/digest/boot/HW-13 verified before the HW-10 corrections |
| Previous HW-12 scoped-stack image | `firmware/build-hermes-hw12-stack-64062cd/stack-chan.bin`; source commit `64062cd`, scoped-stack implementation `f6f0d2d`; 3,919,712 bytes; SHA-256 `f984c5181a48a3cf86a97f9cac59c0584d7c4eeb8a4ad8b81226c972f0cf92a6`; physically verified before the main-task shutter-audio candidate |
| Previous HW-12 ordering image | `firmware/build-hermes-hw12-8bfc589/stack-chan.bin`; source commit `8bfc589`; 3,919,344 bytes; SHA-256 `319006f5c9aa0ed06eb2de906c3da43a1aa022c9606789e816b0044124d6cd60`; physically verified before the scoped-stack candidate |
| Previous HW-11 image | `firmware/build-hermes-hw11-e824ef4/stack-chan.bin`; source commit `e824ef4`; 3,919,184 bytes; SHA-256 `6167fec5380d78fbc6026d6a931169e1f39d0dd5eef12a9897a84f393860cfec`; 24% app partition free; app-only flash/digest/boot/HW-11 verified |
| Previous no-touch app | `firmware/build-hermes-head-touch-fffaba3/stack-chan.bin`; source HEAD `fffaba3`; 3,918,672 bytes; SHA-256 `cf122cd787fae325e38ba3caa2b743e2c4386559d2e46f94e93333d69f8e4551`; physically flashed/verified before the playback-completion corrections |
| Previous expression app | `firmware/build-hermes-expression-bd49497/stack-chan.bin`; 3,918,576 bytes; SHA-256 `78d200403f9d028b690cc50f1d1f7e7d69007c517164506d7f2b09ac5b0ebb2b`; physically flashed/verified before the no-touch correction |
| Previous reconnect app | `firmware/build-hermes-reconnect-launcher-7913742/stack-chan.bin`; 3,918,528 bytes; SHA-256 `ae5ced6a224c0991ff4d9164eec471341cb7b43404bb574762ba9aed9ba2d1a1`; physically flashed/verified before the expression correction |
| Superseded reconnect app | `firmware/build-hermes-reconnect-toast-e73dc30/stack-chan.bin`; 3,918,512 bytes; SHA-256 `7828fa05e4dc8bdd840694050a5c1c24f3df43e3d468c43f0a52e26d4a223050`; physically flashed/verified before its launcher-state defect was isolated |
| Latest isolated Firmware-gate image | 3,918,576 bytes; SHA-256 `4dd63efe2599ef42d37d40a3fa2002101bb917fe0f78ab6a24531ec27da90901`; 24% app partition free; built from the `421457b` expression correction but not flashed |
| Previous expression-correction combined gate | 3,918,576 bytes; SHA-256 `750811cc710e486d8f4f24cae078da1089328da07e05eb595ff81e70b986c986`; 24% app partition free; build evidence only, not flashed |
| Latest no-touch safety isolated gate | 3,918,672 bytes; SHA-256 `f35c24a94d20860d0a709973828035920997e38b1ed934a6d1fbbf3bcc54e43d`; 24% app partition free; startup-qualified three-sample head-touch debounce; build evidence only, not flashed |
| Retained HW-11 correction candidate | `firmware/build-hermes-hw11-e824ef4/stack-chan.bin`; 3,919,184 bytes; SHA-256 `6167fec5380d78fbc6026d6a931169e1f39d0dd5eef12a9897a84f393860cfec`; 24% app partition free; final 363-test host gate and prior 20/20 Firmware CTest/full Firmware gate Green for its source |
| Retained no-touch correction candidate | `firmware/build-hermes-head-touch-fffaba3/stack-chan.bin`; source HEAD `fffaba3`; 3,918,672 bytes; SHA-256 `cf122cd787fae325e38ba3caa2b743e2c4386559d2e46f94e93333d69f8e4551`; 24% app partition free; physically flashed and digest-verified app-only candidate |
| Retained expression candidate | `firmware/build-hermes-expression-bd49497/stack-chan.bin`; 3,918,576 bytes; SHA-256 `78d200403f9d028b690cc50f1d1f7e7d69007c517164506d7f2b09ac5b0ebb2b`; 24% app partition free; physically flashed and digest-verified predecessor |
| Candidate safety configuration | Bridge client, primary USB Serial/JTAG console, USB provisioning and `CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y`; Secure Boot and Flash Encryption remain disabled |
| Latest implementation commits | safe visual helper: `a95319e`; touch metric: `c94efb5`; reconnect observer: `4d129c7`; global notifications: `e73dc30`; launcher-independent state notifications: `7913742`; background task result retrieval: `eef1390`; expression avatar initialization: `421457b`; private-backup discovery: `708084b`; coordinated signal shutdown: `85e2c2a`; head-touch debounce: `e19098d`; physical playback completion: `5bcabc8`; cancel/new-playback isolation: `e824ef4`; deferred camera worker: `8bfc589`; failed-capture propagation/source tracking: `517011a`; scoped camera stack: `f6f0d2d`; main-task shutter audio: `8ad0489`; stable-idle touch re-arm: `9f42b92`; monotonic-deadline audio pacing: `f73ff28`; sustained-touch qualification: `d88f6df` |
| Hermes version | v0.20.0 on a private local host, exposed only through authenticated loopback SSH forwarding |
| Factory backup | PASS; complete 16,777,216-byte image plus partition table and boot log, all mode `0600` under a mode-`0700` ignored local directory |

## HW-01 evidence

- Factory boot was captured before any flash operation. It identified factory Firmware `1.4.4`,
  16 MiB QIO flash, 8 MiB PSRAM and the expected CoreS3/StackChan SKU.
- The checked partition table and the boot log agree exactly:
  `nvs@0x9000/0x4000`, `otadata@0xd000/0x2000`, `phy_init@0xf000/0x1000`,
  `ota_0@0x20000/0x4f0000`, `ota_1@0x510000/0x4f0000`,
  `assets@0xa00000/0x400000`, and `coredump@0xe00000/0x10000`.
- A single 16 MiB stub read was rejected after a short serial frame. A Red test reproduced the
  unsafe all-at-once assumption; commits `b515105` and `7ec4114` keep native USB attached, split
  the read into sixteen 1 MiB regions, validate the esptool device digest for every region and
  retry only a failed region.
- The protected run completed all 16 regions with matching device digests and zero retries. The
  separately read partition table is 3,072 bytes and parses successfully with ESP-IDF v5.5.4
  `gen_esp32part.py`.
- Stored SHA-256 sidecars were independently recomputed and passed. The copied boot log hash
  matches the pre-flash source log. A final read-only `esptool.py verify_flash` compared the saved
  16 MiB image with the device and reported `verify OK (digest matched)`.
- The raw serial identity, boot log, image, metadata, checksums and restore command remain ignored
  local evidence and are not committed. No write was attempted until this evidence was complete.

## Approved flash and boot evidence

- After the PC restart, Windows still listed the reviewed K151 as the only intended shared USB
  device. WSL attachment again produced exactly one stable `/dev/serial/by-id` path with the same
  reviewed identity. The raw identity remains private.
- Before writing, a second read-only whole-device `verify_flash` compared the complete 16 MiB
  factory backup with the device and reported a matching digest. The retained partition table was
  byte-identical to the verified factory table, and the generated configuration still enabled the
  Bridge client, USB provisioning and physical head-motion lock.
- With explicit user approval, the retained 3,921,696-byte application at that checkpoint,
  SHA-256 `cbfb346d603b5b82c8d1ed68ee734ff5cfab251d038bbf64d65d90853117090d`, was flashed through the
  generated esptool `@flash_args` against `<reviewed-stable-port>`. Bootloader, partition table,
  application and assets writes each passed esptool's post-write hash check. The device then
  selected `ota_0`; its OTA sequence and CRC were valid.
- The first custom boot exposed a deterministic provisioning-console defect: ESP-IDF rejected a
  zero-length line-history setting, followed by a `LoadProhibited` panic and reset loop. This run
  was not accepted. The device was halted in the ROM downloader while the defect was addressed.
- A failing Firmware contract test first required the minimum valid one-entry RAM history and
  explicit history cleanup. Commit `fca58cf` then made the minimal production change. The complete
  `./scripts/verify.sh` gate passed before the replacement image was written.
- Only the corrected application partition at `0x20000` was reflashed against the same reviewed
  stable port because the other retained artifacts were unchanged. A read-only application
  `verify_flash` then matched SHA-256
  `b6547eab0d8c5b1e62bb3980076c0d66a52affc1b65e3052fd9f4769736a2d4e`.
- A 35-second post-reset serial observation saw one Firmware `1.5.1` boot, the USB provisioning
  prompt, camera initialization and servo initialization. It saw no ROM reboot, software reset,
  panic, `LoadProhibited`, provisioning-start failure or watchdog marker; the last ESP log
  timestamp was 30.794 seconds. This duration is an observation window, not a latency result.
- The build-time physical head-motion lock remained enabled. No physical display, touch, Wi-Fi,
  Bridge, speaker, LED, camera-capture or neck-motion behavior was claimed from the serial log.

## USB provisioning, Wi-Fi and first LAN blocker evidence

- The corrected boot image still configured the provisioning REPL as ESP-IDF's secondary USB
  console. That mode is output-only, so a physical Enter or command could not reach the REPL. A
  failing Firmware contract test first required
  `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y`; commit `ab7f1e4` made USB Serial/JTAG the primary console
  and extended the final gate. After an app-only reflash and digest verification, Enter produced
  `hermes-config>`, an invalid command returned the documented usage error, and the prompt
  recovered without reset.
- Physical `set-device-id` and `set-url` writes succeeded, but `set-discovery disabled`
  deterministically aborted with `ESP_ERR_NVS_KEY_TOO_LONG`: the physical NVS key
  `discovery_enabled` exceeded ESP-IDF's 15-byte key limit. A new failing contract test captured
  that limit. Commit `a6c882e` shortened both the write and read side to physical key
  `bridge.discovery`; the original logical requirement remains recorded in `Goal.md`.
- The complete gate then passed with 328 host tests and 18/18 Firmware CTest targets. The retained
  3,918,272-byte app at that checkpoint was reflashed only at `ota_0@0x20000`; bootloader,
  partition table, NVS and assets were not written. Both esptool's post-write hash and a read-only
  `verify_flash` digest comparison passed. The formerly crashing discovery command then returned
  `OK saved; reboot required` on the physical device.
- Device ID, fixed Bridge URL, disabled discovery, enabled touch and a fresh random device token
  were provisioned successfully. The serial utility retained responses only in memory, suppressed
  their content, and printed no token. The Firmware line editor can echo typed input, so no
  recorded terminal monitor was used for the token command. No token was written to the
  repository or a host file.
- With a temporary local Bridge running, a 45-second redacted boot observation saw exactly one
  Firmware boot, a valid Bridge configuration, Wi-Fi station startup and IP acquisition on the
  same `/24` as the Bridge host. It saw no Wi-Fi configuration mode, panic, abort, software reset
  or watchdog marker. This proves the physical Wi-Fi slice, not WebSocket connectivity or
  latency.
- The device never reached the Gateway: Control API metrics remained zero for authenticated
  connects, disconnects and auth failures. A separate 50-second redacted observation identified
  `EspTcp`/`WebSocket` connect failure with socket errno 113 (host unreachable), before any HTTP
  upgrade or authentication.
- Read-only host checks at that checkpoint showed WSL mirrored networking, a live loopback Control API, Windows
  ownership of the selected LAN IPv4, WSL Hyper-V firewall `DefaultInboundAction=Block`, and no
  TCP 8765 rule. Windows itself could not reach that LAN-address port. The Bridge was shut down
  cleanly and its process-only token discarded. No firewall or other OS setting was changed in
  that first attempt; the later explicitly approved retry is recorded below.

## Authenticated Bridge, corrected identity and display evidence

- Two physical defects were isolated with failing tests before production changes. Optional
  command-envelope fields are now omitted instead of serialized as JSON `null` (`4abe3d9`), and
  all Firmware identity responses use the board identity `M5STACK-K151` rather than a transport
  name (`0a3bad2`). The complete gate then passed with 330 Python tests, 18/18 Firmware CTest
  targets and a fresh motion-locked ESP-IDF build.
- With explicit user approval, only the retained 3,918,256-byte application was written to
  `ota_0@0x20000` on the single reviewed device. Bootloader, partition table, NVS and assets were
  not written. Esptool's post-write hash passed, and a separate read-only application
  `verify_flash` reported `verify OK (digest matched)`. A subsequent 20-second nonprinting serial
  observation found no panic, abort, watchdog or reboot-loop marker; this is an observation
  window, not a latency result.
- The first fresh-token Bridge start correctly failed closed because no Hermes API key was
  configured. For the hardware-only retry, a replacement random device token and a process-only
  placeholder Hermes key were kept only in memory; no Hermes conversation API was called and no
  secret was printed or saved.
- The user explicitly approved one temporary Windows Hyper-V rule named
  `StackChanHermesBridge8765`. Its reviewed scope was inbound Allow, TCP local port 8765,
  `LocalSubnet`, and only the WSL Hyper-V VM creator. The default inbound action remained Block.
  Earlier bounded sessions removed the rule on completion. For the current continuous hardware
  campaign, the operator instructed that exactly one copy be retained until final Goal cleanup;
  while idle there is no listener on 8765/8766 and the default inbound action remains Block.
- The physical Firmware authenticated and sent hello as device `stackchan-001`, Firmware `1.5.1`,
  hardware model `M5STACK-K151`, with microphone, speaker, camera, touch, display and avatar
  capabilities true, 12 LEDs, and head capability false. Bridge liveness was Green and the
  connected-device count was one.
- Read-only `device.get_status` and `device.get_info` each returned HTTP 200 with `ok=true` while
  the device stayed connected. Both reported `M5STACK-K151`; the observed state was IDLE. These
  values prove authenticated status transport, not command latency.
- The first physical display command had returned HTTP 200 but had no observer. Commit `b7b2830`
  then moved `display.show_text` from the avatar-only chat bubble to a global toast. On its first
  physical use that image timed out once, disconnected once and automatically reconnected. Code
  review implicated lazy toast-ability creation while Mooncake was updating its ability manager;
  this mechanism is a strongly supported inference, not a serial-proven panic.
- A failing contract test required global toast-manager initialization before both the Bridge
  worker and the first Mooncake update. Commit `6faa72e` made initialization explicit and
  idempotent, retained lazy-call safety, and added the missing include guard found by the clean
  compiler. The complete gate passed with 332 Python tests, 18/18 Firmware CTest targets and a
  fresh motion-locked ESP-IDF build.
- After a new explicit approval, only the retained 3,918,448-byte application, SHA-256
  `ed581f4ad8374325729558233da2dbde329f58d5732e0254f3b2b5ad7e26dc79`, was written to
  `ota_0@0x20000`. Bootloader, partition table, NVS and assets were not rewritten. Esptool's
  post-write hash and an independent read-only application `verify_flash` both matched.
- In the final observed run, one `M5STACK-K151` stayed authenticated with `head=false`.
  `display.show_text` for `HERMES OK 0831` returned HTTP 200 with `ok=true` in 174 ms, and the
  operator independently confirmed seeing the text on the physical LCD. During the following
  20-second observation, connected devices stayed at one while disconnect and command-timeout
  counters stayed zero. This is display behavior evidence; the timing is one observation, not a
  latency claim.
- During a separate 45-second touch prompt, no audio frame, active turn, disconnect or reconnect
  event was observed. At that checkpoint touch behavior remained unverified despite the now-Green
  physical display slice. This historical failed prompt was superseded by the corrected deliberate-
  touch observation recorded below.
- The first attempt produced a 2237.4 ms observer value, but its replacement Bridge exited because
  the orchestration did not keep a TTY open. That attempt was rejected as invalid rather than
  reported as reconnect performance, and a fresh authenticated session was established.
- The valid bounded HW-05 run used the GET-only observer from `4d129c7`, two confirmed-loss samples,
  a deliberate 3.0-second Bridge-down hold and a TTY-held replacement Bridge. The target
  re-registered as the same `M5STACK-K151` with `head=false` in **4052.5 ms** measured from the
  first confirmed-outage sample. This is the observer's confirmed-outage-to-re-registration
  interval and includes the deliberate hold; it is not pure transport reconnect latency.
- A simultaneous read-only serial monitor completed without error, observed seven bytes and saw
  no `ESP-ROM`, `rst:`, Guru Meditation or abort marker. This supports “no reset marker observed”
  only; the sparse window does not prove that a Firmware reboot was impossible. The replacement
  Bridge reported one connected device and zero disconnect, timeout, touch, audio-input and active
  turn counters after re-registration.
- The operator reported no screen change after that Bridge restart. Inspection showed that the
  existing `Connecting Bridge` status used the launcher-inapplicable avatar speech path. A failing
  contract test preceded `e73dc30`, which routed `Connecting Bridge` and `Bridge connected` to the
  global notification API while retaining avatar status/emotion updates.
- After explicit approval, the single stable device, private identity metadata, verified factory
  backup, 3,918,512-byte candidate SHA-256, `head` output lock and one-entry app flash definition
  were all revalidated. The previously flashed `6faa72e` app matched read-only before the write.
  Only `ota_0@0x20000` was written from
  `firmware/build-hermes-reconnect-toast-e73dc30/stack-chan.bin`; bootloader, partition table, NVS
  and assets were untouched. Esptool's post-write hash and a separate read-only digest comparison
  both passed. A 30-second boot window saw Firmware `1.5.1` once and no panic, watchdog or reboot
  loop marker.
- In the resulting controlled restart, the GET-only observer confirmed loss twice and measured
  **9461.9 ms** to re-registration, including a deliberate 3.0-second down hold. The same
  `M5STACK-K151` returned with `head=false`; a simultaneous serial window saw 183 bytes and no ROM,
  reset, panic or watchdog marker. The operator saw neither reconnect notification, so the
  `e73dc30` physical presentation was rejected rather than marked Green.
- A manual global `display.show_text` request initially returned HTTP 422 because the required
  priority was omitted and therefore never reached the device. Corrected short requests returned
  HTTP 200 but were missed by the observer; a corrected 30-second `DISPLAY PATH OK` request
  returned HTTP 200 and was independently visible. This isolated the display/toast subsystem as
  working and the reconnect state invocation as faulty.
- Source inspection found that state notifications were still inside `display->IsSetupUICalled()`;
  the launcher leaves that avatar-UI flag false. A new failing contract test required an
  independent notification dirty flag and notification block outside that guard. Commit `7913742`
  made the minimal change while retaining avatar-only presentation behind the original guard. The
  focused Firmware contract suite passed 23/23, the host gate passed 343 tests, and the complete
  gate passed 343 host tests, 18/18 Firmware CTest targets and a fresh 3,918,528-byte ESP32-S3
  build with 24% app headroom.
- A new retained build from `7913742`, SHA-256
  `ae5ced6a224c0991ff4d9164eec471341cb7b43404bb574762ba9aed9ba2d1a1`, was approved separately.
  The same one-device identity/backup/hash/config/port guards passed; read-only comparison matched
  the current `e73dc30` app before the write. Again, only `ota_0@0x20000` was written. Esptool's
  post-write hash and an independent read-only app digest comparison passed. A deliberate-reset
  30-second boot window captured 12,871 bytes, one Firmware `1.5.1` marker, one expected ROM/reset
  marker and no panic, watchdog, additional reboot or reboot-loop marker.
- The final controlled HW-05 run started from one authenticated K151 with `head=false` and zero
  disconnect/auth-failure/timeout/touch/audio/active-turn metrics. The observer confirmed loss
  twice and measured **15,697.6 ms** from first confirmed outage to the same target's
  re-registration, including the deliberate 3.0-second hold. A simultaneous 25-second serial
  window captured 186 bytes with zero ROM, reset, panic or watchdog marker. Replacement-process
  metrics again showed one connected device and zero disconnect, auth-failure, timeout, touch,
  audio and active-turn values.
- The operator independently saw both `Connecting Bridge` and `Bridge connected`, completing the
  reconnect-presentation slice. `Connecting Bridge` appeared lower in the toast stack instead of
  replacing the top toast; this remains a recorded UX follow-up but both required states were
  visible. HW-05 is therefore PASS within the controlled observation boundary.
- The first Bridge shutdown also surfaced an already-failed background voice-turn task as
  `Task exception was never retrieved`. No audio command was sent, debug persistence was disabled,
  no media was retained and the placeholder configuration stopped before a live provider request;
  the event is not counted as HW-02/HW-07 evidence. A failing unit test reproduced the unobserved
  task failure before `eef1390` added a done callback that retrieves the result. The related
  audio-input, voice-turn and runtime suite passed 13 tests.
- Eight safe non-motion commands set and restored avatar expression, a dim blue LED state,
  brightness and volume. Every command returned HTTP 200 with `ok=true`, and connectivity remained
  stable. No head/servo command was sent, and visual/acoustic effects were not independently
  confirmed. The physical motion lock remained enabled throughout.
- The attended `--safe-visual` path was subsequently invoked against the authenticated K151. It
  applied a happy expression, dim blue LEDs `(0,16,64)` and brightness 35, held for 20 seconds,
  then restored brightness 70, cleared the LEDs and restored idle. The command exited 0; connected
  devices remained one and disconnect, timeout, touch, audio-input and active-turn counters stayed
  zero. The operator did not confirm seeing the effects, so this is safe-command/restore transport
  evidence rather than visual confirmation and HW-04 remains PARTIAL.
- A later attended session reprovisioned a fresh random device token without printing or saving it
  on the host. The first reset attempt did not produce a device registration and was rejected
  without sending any body command. A read-only `flash_id` operation then supplied a verified
  default/hard reset, after which one Firmware `1.5.1` K151 registered with display/touch/avatar
  true and `head=false`.
- The motion-free visual sequence was run for 45 seconds and, after the operator missed that
  window, repeated for 30 seconds. Each run requested happy, dim blue LEDs `(0,16,64)` and
  brightness 35, then restored brightness 70, cleared the LEDs and restored idle. Both runs exited
  0 and attempted every restore. Connected-device count remained one; disconnect, authentication
  failure, command-timeout, touch, audio-input/output and active-turn counters stayed zero.
- The operator independently saw the screen brightness change and blue LEDs in the repeated run,
  so those two HW-04 effects are physically Green. No recognizable happy expression appeared.
  Source inspection showed the flashed launcher never called `SetupUI()`: `setExpression()` still
  returned success while `SetEmotion()` discarded the request because no avatar existed.
- A failing Firmware contract test captured that false success before commit `421457b` made an
  explicit expression command initialize the avatar, verify its existence and prevent a deferred
  idle state from overwriting the requested expression. The focused test and full Firmware
  contract suite pass, Firmware CTest is 18/18, and a fresh 3,918,576-byte build with 24% free
  completed.
- On 2026-09-01, a new explicit app-only approval preceded a complete preflight. The same one
  stable USB identity was present; the ignored 16 MiB factory image and partition sidecar hashes
  recomputed successfully; the device reported ESP32-S3 rev 0.2, Secure Boot disabled, Flash
  Encryption disabled and `SPI_BOOT_CRYPT_CNT=0`; and a read-only comparison proved that the
  current 3,918,528-byte `7913742` app still matched. The retained expression candidate hash,
  motion lock, primary USB settings, byte-identical partition table and one-entry
  `0x20000 stack-chan.bin` argument file were rechecked before writing.
- Only the 3,918,576-byte retained candidate was written at `ota_0@0x20000`; bootloader, partition
  table, NVS and assets were untouched. Esptool completed in 18.9 seconds with its write hash
  verified, and a separate read-only `verify_flash` reported `verify OK (digest matched)` against
  the retained candidate. Two preliminary nonprinting monitor attempts did not capture a boot
  marker and were rejected; the one monitor process that retained the serial lock was identified
  exactly and terminated. A clean exclusive 30-second deliberate-reset observation then captured
  13,086 bytes, one Firmware `1.5.1` marker, one expected `ESP-ROM`/`rst:` pair and no Guru
  Meditation, LoadProhibited, abort or watchdog marker.
- With separate approval, the exact WSL-only TCP 8765 `LocalSubnet` firewall rule and a fresh
  response-suppressed NVS device token were used for one bounded hardware-only session. No real
  Hermes endpoint was configured. Exactly one authenticated `M5STACK-K151` registered as Firmware
  `1.5.1` with avatar/display true, 12 LEDs and `head=false`. Before the command, connected devices
  was one while disconnect, authentication failure, timeout, touch, audio-input and active-turn
  metrics were all zero.
- After a five-second attended lead-in, an expression-only request applied happy for 20 seconds.
  Both happy and the `finally`-guarded idle restore returned `ok=true`; the operator independently
  saw the happy eyes. Post-command metrics still showed one connected device and zero disconnect,
  authentication failure, timeout, touch, audio-input and active-turn values. This run sent no LED,
  brightness, volume, head, camera, microphone or playback command. Expression is physically
  Green; HW-04 remains PARTIAL only because acoustic volume and safely bounded head/home motion
  are not established.
- At that earlier checkpoint, no camera command was sent because explicit privacy consent had not
  been received. Audio,
  live Hermes, STT and TTS scenarios were not run. After evidence collection, the Bridge was
  stopped, process-only secrets were discarded and the exact temporary firewall rule was removed.
  The PTY stop completed but exposed Uvicorn re-raising SIGINT while its peer lifespan was still
  closing. A failing host test reproduced that trace before `85e2c2a` retained the conventional
  exit code 130 without re-raising the captured signal. A two-server loopback reproduction then
  exited 130 with no traceback.
  Final checks found zero matching firewall rules, default inbound Block, no Bridge process or
  8765/8766 listener, no attached WSL serial device and none of the session temporary targets.

## HW-06 fixed Japanese audio-output evidence

- Two early speech trials are rejected as Japanese-content evidence. Windows PowerShell 5.1 read a
  BOM-less UTF-8 `.ps1` file as an ANSI code page, so its literal Japanese text became mojibake
  before Microsoft Haruka synthesis. The first was inaudible and the later high-gain versions were
  audible but unintelligible; this was a defective test stimulus, not evidence of a Firmware or
  Bridge playback defect.
- A deterministic two-beep isolation stimulus then exercised the same Bridge-to-device route. The
  host Opus round trip remained nonzero, the K151 decoded and resampled all 20 frames, both beeps
  were heard on each of two plays, state returned to IDLE, and underflow, overflow, decoder, codec,
  disconnect, authentication and timeout indicators stayed zero. This independently established
  the Opus decoder, resampler, I2S and internal-speaker path before evaluating language content.
- The corrected source constructed `こんにちは。` from explicit Unicode code points rather than a
  script-file Japanese literal. Windows Japanese recognition returned exactly `こんにちは` for the
  raw source with confidence `0.963` and for the final processed candidate with confidence `0.9625`;
  the mojibake source was not recognized. The final temporary candidate was 57,678-byte mono PCM16
  at 16 kHz, 1.8 seconds long, with SHA-256
  `ffb45d626fcbf1c15058dd839658fd27535b64d8a9dea5ce226e526975346148`, peak `0.480011`, RMS
  `0.132079` (-17.58 dBFS) and 336 ms leading protection. It was not added to the repository.
- Host validation encoded 30 Opus frames with a maximum packet size of 146 bytes. Decode produced
  peak `0.478577`, RMS `0.126737` (-17.94 dBFS), an active interval of 0.450–1.312 seconds and zero
  codec errors.
- The final attended run rechecked that exact candidate digest, registered one K151 running
  Firmware `1.5.1` with `speaker=true` and `head=false`, changed volume `70 → 85 → 70`, and sent the
  30 Opus frames once. The device logged one 16-to-24 kHz resampler start and one output enable;
  Bridge/device counters recorded zero disconnect, authentication failure, timeout, underflow,
  overflow, device error, audio input, touch and active-turn deltas. State returned to IDLE and the
  original volume 70 was restored.
- When explicitly asked to assess intelligibility, the initial syllable and clipping, the operator
  reported that the fixed Japanese phrase was properly audible. No initial-syllable loss or sound
  breakup was reported. This completes HW-06. It does not establish comparative HW-04 volume gain,
  microphone input, live TTS quality or playback latency.
- After the run, Bridge processes and temporary audio/script files were removed, USB was detached,
  and there was no listener on 8765/8766. Per the operator's continuous-test instruction, exactly
  one approved WSL-VM/TCP-8765/`LocalSubnet` rule is retained until final Goal cleanup; default
  inbound remains Block.

## No-touch volume comparison and input-safety finding

- One attended public-Protocol-v1 harness generated a deterministic 1.5-second, 25-frame two-beep
  Opus stimulus and sent the exact same packet sequence first at volume 45 and then at 85. The
  original volume 70 was restored in `finally`. Both post-playback states were IDLE; disconnect,
  protocol-error, playback-failure, decode, codec, panic and watchdog counts were zero. Serial
  evidence included the expected 16-to-24 kHz resampler, output enable and volume 45/85/70 actions.
- The operator confirmed that the second volume-85 play was clearly louder than the first
  volume-45 play. Because the exact same Opus packet sequence was reused and all restoration/error
  evidence remained Green, comparative HW-04 volume is physically Green.
- The harness rejected its own overall result because it observed exactly two input-lifecycle
  notifications. The physical Firmware maps head-sensor `Press`/`Release` directly to
  `audio.input.start` / `audio.input.end`; it does not emit the separately counted `touch.*` event
  family from this path. After the run, the operator confirmed touching nothing. This is therefore
  classified as a no-touch false activation, not a successful attended touch or microphone test.
- No incoming audio content was saved, printed, transcribed or analyzed. Debug persistence was not
  enabled and the runtime-only token was discarded. At the time, this was not HW-07 acceptance:
  the later corrected deliberate touch was HW-02 trigger evidence only, while full microphone
  acceptance still required separate privacy consent.
- The session restored volume 70, stopped the WebSocket listener, detached BUSID 1-6 back to
  `Shared`, deleted its temporary scripts/cache and left no listener on 8765/8766. The single
  approved Hyper-V TCP-8765 rule remains enabled and scoped as before, retained until final Goal
  cleanup.
- A failing host test first required startup touch noise to remain silent. After the smallest
  startup-baseline Green, triangulation failed with `stable touch did not emit a press`; the final
  `e19098d` `HeadTouchDebouncer` requires stable idle before arming and three consecutive samples
  for both press and release. Long startup activation and one/two-sample operational noise tests
  are Green.
  The full Firmware host suite passes 19/19, and a fresh motion-locked ESP-IDF image is 3,918,672
  bytes with 24% free and SHA-256
  `f35c24a94d20860d0a709973828035920997e38b1ed934a6d1fbbf3bcc54e43d`. This was temporary build
  evidence; the separately retained image below was later flashed. The no-touch observation later
  passed, followed by the Green deliberate-touch observation recorded below.
- The final combined gate then repeated all 352 host tests, passed 19/19 Firmware CTest and built a
  separate 3,918,672-byte image with 24% free and SHA-256
  `391d06617aab21bc2e1106faec8ce5d872bcc4bc3217e80dcea1699cbd4bf39a`. It is temporary build
  evidence only and was not flashed.
- A separate retained build from source HEAD `fffaba3` produced
  `firmware/build-hermes-head-touch-fffaba3/stack-chan.bin`: 3,918,672 bytes, 24% free, SHA-256
  `cf122cd787fae325e38ba3caa2b743e2c4386559d2e46f94e93333d69f8e4551`. Esptool reports a valid
  checksum and validation hash. Its mode-0600 generated configuration enables Bridge, USB
  provisioning, primary USB Serial/JTAG and `CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y`, while
  Secure Boot and Flash Encryption remain disabled. Its partition table and app-only arguments
  match the verified factory/predecessor layout; the sole address/image entry remains
  `0x20000 stack-chan.bin`.
- The subsequent read-only flash preflight found exactly one stable WSL serial identity and one
  16 MiB factory image. Factory/partition sidecar digests, restore metadata and the pre-flash boot
  log all revalidated. The device remained ESP32-S3 rev 0.2 with Secure Boot disabled,
  `SPI_BOOT_CRYPT_CNT=0` and Flash Encryption disabled; the current expression app still matched
  its retained digest. The candidate hash, factory-identical partition table, single app argument,
  required Bridge/USB/motion-lock settings and implementation commit were rechecked successfully.
  At that checkpoint no write command had been executed.
- The app-only flash was explicitly approved after that preflight. Esptool wrote only the
  3,918,672-byte app at `ota_0@0x20000` in 19.9 seconds; bootloader, partition table, NVS and assets
  were untouched, and its write hash passed. An independent read-only comparison then reported
  `verify OK (digest matched)`. A content-suppressed 30-second reset/boot observation counted
  12,679 bytes, one Firmware `1.5.1` marker and two reset markers, with zero panic, abort or watchdog
  markers. The temporary observer was deleted. The correction is installed, but a separately
  consented behavioral regression was still required at that checkpoint.

## Verified no-touch regression after correction

- The consented observation used one stable serial identity, a fresh response-suppressed process-
  only token and the existing scoped firewall rule. Preliminary setup attempts failed closed before
  any listener-backed observation; a non-mutating probe isolated USB-console `LF` handling and a
  required REPL-prompt wait. No preliminary attempt counted as behavioral evidence.
- The final authenticated `M5STACK-K151` / Firmware `1.5.1` connection advertised `head=false` and
  remained stable for 60.03 seconds with `quiet=true`.
  The observation confirmed that audio-input start/end, frames, discarded bytes and device events all remained zero.
  Therefore no audio content was received, saved, printed, transcribed or analyzed, and no
  playback, body, camera or head command was sent.
- After the window, the operator confirmed touching neither the device, desk nor cable. This makes
  the corrected no-touch regression physically Green. By itself it did not establish deliberate
  touch or HW-07 microphone input; the separately consented touch-only follow-up is recorded below.
- The listener count returned to zero, the serial identity remained unique, and temporary observer,
  test and probe sources plus bytecode were deleted. The process-only token was discarded. USB stays
  attached for the next approved hardware check, while the single firewall rule remains retained
  until final Goal cleanup.

## Verified deliberate-touch observation after correction

- After separate privacy consent, a production-Gateway observer authenticated one
  `M5STACK-K151` / Firmware `1.5.1` connection with `head=false`. It remained stable for 51.11 seconds
  with zero input disconnects and zero device events.
- At the explicit observation signal, the operator touched once for approximately one second,
  released and did not speak. After the run, the operator confirmed one approximately one-second touch/release and no speech.
- The direct head-sensor audio lifecycle reported one `touch` start and one `silence` end. Exactly
  25 Opus frames and 3,617 bytes were counted and immediately discarded; the observer reported
  `single_touch_green=true`, `trigger_touch=true` and `end_reason_silence=true`.
- No audio content was saved, printed, replayed, transcribed or analyzed. No playback, body, camera
  or head command was sent. The observer, runner, tests and bytecode were deleted, the process-only
  token was discarded, the serial identity remained unique, and there was no listener on 8765/8766.
  A final read-only Windows query reconfirmed exactly one enabled `StackChanHermesBridge8765` rule:
  Inbound Allow, TCP 8765, `LocalSubnet`, scoped to the WSL Hyper-V VM creator.
- This proves normal corrected physical touch behavior and completes HW-02. It does not complete
  HW-07: no WAV was reconstructed, no microphone volume/noise was assessed, and neither spoken-
  utterance ending nor maximum-duration stopping was exercised. At that checkpoint HW-07 was NOT RUN
  and required the separately consented microphone acceptance scenario recorded next.

## Verified HW-07 physical audio input

- The first approved diagnostic attempt used a 90-second operator-response timeout and had already
  stopped before the later physical action. It produced no accepted audio result and left no WAV,
  so it is rejected as behavioral evidence. A failing harness test then required at least a
  600-second attended timeout; the bounded synthetic capture, cleanup, formatting, lint and type
  checks were Green before the successful retry.
- The accepted production-Gateway session authenticated exactly one stable `M5STACK-K151` running
  Firmware `1.5.1`, with `microphone=true` and `head=false`. A five-second no-touch pre-signal window
  had no unsolicited input. There were zero input disconnects and no playback, body, camera or head
  command was sent.
- In the short-speech path, one touch delivered 68 Opus frames / 9,946 bytes over 4.08 seconds. The
  temporary WAV was reconstructed, reopened and validated at mode `0600`. Numeric-only analysis
  measured full RMS 553.8172, speech RMS 1996.7531, noise RMS 123.1321, peak 12012, SNR 24.1991 dB,
  400 ms accepted speech, zero decode errors and `volume_ok=true`, `noise_ok=true`,
  `clipping_ok=true`. VAD accepted the utterance and ended it for `silence`.
- In the separate intentionally silent maximum-length path, a held touch delivered
  248 Opus frames / 36,329 bytes over 14.88 seconds and stopped for `max_duration`.
  The operator confirmed approximately 20 seconds of touch, no speech and a final release.
  Its reconstructed/reopened mode-`0600` WAV had noise RMS 116.5341 and zero decode errors. Because
  this stimulus was intentionally silent, `vad_accepted=false` and `volume_ok=false` are expected
  and are not claimed as speech-quality evidence. `clipping_ok=true` is only the configured
  clipping-fraction threshold result; peak 32767 means this report does not claim zero clipped
  samples.
- Each WAV existed only inside a mode-`0700` temporary directory, was cleared from memory and
  deleted immediately after numeric analysis. Both results reported `wav_deleted=true`; the
  aggregate reported `private_files_remaining=0`, stable authentication/connection and
  `hw07_green=true`. There was no replay, transcription, external service, cloud service or Hermes
  processing. Temporary harness sources and bytecode were also deleted, the process-only token was
  discarded, the serial identity stayed unique, and there was no listener on 8765/8766 afterward.
  The one scoped firewall rule remains retained until final Goal cleanup.

## Verified HW-11 physical cancellation

- Firmware regression tests first exposed two completion/cancellation races. Commit `5bcabc8`
  prevents empty software queues from reporting IDLE while a frame is still in physical output.
  Source commit `e824ef4` then resets the decoder on every new `SPEAKING` stream, tracks an
  in-flight decode generation, invalidates that generation on cancel and discards any decoded frame
  that returns stale. The full host/Firmware gates passed with 20/20 Firmware CTest before hardware
  use.
- The retained candidate is
  `firmware/build-hermes-hw11-e824ef4/stack-chan.bin`, 3,919,184 bytes, SHA-256
  `6167fec5380d78fbc6026d6a931169e1f39d0dd5eef12a9897a84f393860cfec`, with 24% of the app
  partition free. Its checksum/validation hash, one-entry `0x20000 stack-chan.bin` partition
  mapping, Bridge/primary-USB/provisioning/motion-lock configuration, one stable serial identity,
  verified 16 MiB backup and unchanged security state all passed read-only preflight. After explicit
  approval, only the app at `0x20000` was written; esptool's write hash and an independent
  `verify_flash` digest both matched. A content-suppressed 30-second boot captured 12,494 bytes,
  one each of the ROM, project and app markers and zero panic, abort, watchdog or assertion markers.
- Two diagnostic runs were deliberately rejected before acceptance. A first high/low run could not
  distinguish a lost second turn from an unsuitable stimulus. An isolated 440 Hz playback entered
  `SPEAKING`, sent all 20 frames, completed and returned IDLE, but the operator heard nothing. It
  also unexpectedly produced one input start, 44 input frames and one input end while the operator
  reported no contact. Every packet was immediately discarded; no audio was saved, printed,
  replayed, transcribed or externally processed. The run failed closed and is not accepted as HW-11 evidence.
  The lifecycle remains a historical intermittent no-contact input-safety finding; its cause is
  unknown, and this report does not infer speaker vibration or any other mechanism without further
  evidence. The bounded follow-up below did not reproduce it.
  The next audible 880/880 Hz run produced the expected human observation but one
  aggregated audio-queue event, whose kind had not yet been separated, so that run was also
  rejected. A failing diagnostic-harness test preceded separate underrun/overflow counters.
- In the accepted attended run, the first 30-frame 880 Hz stream used a 1.8-second bounded Mock-TTS
  stimulus. The cancel request began approximately 678 ms after host streaming began; the reported
  request/response interval was `cancel_after_ms=1957.6`, of which cancel latency was 1279.7 ms.
  The command succeeded and the device reported IDLE after cancellation. Following a 1250 ms gap,
  a second distinct 20-frame 880 Hz stream entered `SPEAKING`, completed under a new turn ID and
  returned to IDLE. Authentication and the connection stayed stable, with
  `audio_underrun_events=0`, `audio_overflow_events=0`, zero device errors and zero audio-input
  start/frame/end events.
- The operator described the physical result as a short first beep followed by a longer second beep,
  confirming both interruption and subsequent playback. The operator touched neither the device, desk nor cable.
  The machine classifier was Green before the independent operator report;
  together they make HW-11 PASS. No live TTS, STT, Hermes, persisted media, camera, body or head
  operation was used. The process-only credential was discarded, the serial identity remained
  unique, and both WSL and Windows had no listener on 8765/8766 afterward. The single scoped
  firewall rule remains retained until final Goal cleanup.

## Verified bounded no-contact silent/440/880 comparison

- A separately attended bounded silent/440/880 comparison used the production Gateway and output
  streamer with a process-only credential. Its six 1.2-second, 20-frame phases were ordered
  `silent_a → 440_a → 880_a → silent_b → 880_b → 440_b`, counterbalancing the two silence, 440 Hz
  and 880 Hz conditions. The first attended wait expired before any stimulus was sent; a failing
  harness test preceded extending the human-response window and replacing its thread-backed wait
  with asynchronous polling. The nine temporary harness tests, Ruff and strict mypy then passed before
  the accepted retry.
- All six phases started IDLE, entered `SPEAKING` after all 20 frames were sent, completed, and
  returned IDLE. Authentication, the original connection identity, K151/Firmware identity and
  `speaker=true`/`head=false` remained stable. Across every phase,
  input starts, frames and ends all remained zero; `bytes_discarded=0`, `touch_event_count=0`,
  `audio_underrun_events=0`,
  `audio_overflow_events=0`, `queue_error_events=0` and device-error events were also zero.
- The operator heard two separated 880 Hz tones and confirmed touching neither the device, desk nor cable
  throughout the comparison; no incoming audio content existed to retain or process. No media
  was saved and no external processor, STT, Hermes, camera, body or head operation was used. Combining
  the valid machine measurement with that independent physical observation makes the bounded
  input-safety follow-up Green (`finding_reproduced=false`, `input_association=none`).
- The earlier isolated 440 Hz event remains a historical intermittent no-contact input-safety
  finding and was not reproduced in this bounded comparison. One bounded non-reproduction neither
  identifies its cause nor proves a permanent correction. The process-only credential and temporary
  harness were discarded after recording aggregate evidence; both WSL and Windows again had no
  listener on 8765/8766. The single scoped firewall rule remains retained until final Goal cleanup.

## Failed HW-12 camera diagnostic

- A failing Firmware test first reproduced that camera work could begin inside command handling and
  prevent the command result from reaching the Bridge before its five-second deadline. Source
  commit `8bfc589` queues the request in `start()` and starts the worker only from the later camera
  update phase, after the network client has sent the command result.
- The retained candidate is
  `firmware/build-hermes-hw12-8bfc589/stack-chan.bin`, 3,919,344 bytes, SHA-256
  `319006f5c9aa0ed06eb2de906c3da43a1aa022c9606789e816b0044124d6cd60`, from source commit
  `8bfc589`. Its approved app-only write at `0x20000` and independent read-only digest comparison
  both passed. A content-suppressed deliberate-reset observation captured 12,627 bytes with the
  expected ROM/reset/project/version markers and zero panic, watchdog or assert markers.
- After separate explicit camera consent, exactly one production Control/Gateway request used
  quality 70, a 2 MiB limit, expected 320×240 dimensions and nonpersistent storage. It returned the
  command result instead of the predecessor's `COMMAND_TIMEOUT`, then ended at `CAPTURE_TIMEOUT`
  after 45 seconds. This proves the ordering correction only; it does not prove that a JPEG was
  captured or that an upload reached the Gateway. There was no retry.
- No image was displayed, viewed, externally processed or retained. No capture identifier, image
  bytes, image hash, device token or content was printed or committed; no Hermes, STT, TTS or other
  external processor was used, and the capture store was empty afterward.
- Diagnosis then found that the Bridge ignored an owned `camera.completed(ok=false)` while waiting
  for an upload, masking Firmware failures as the full capture timeout. A failing coordinator/event
  test preceded commit `517011a`, which validates ownership, wakes the waiter and maps the event to
  `CAPTURE_FAILED`. The same Red→Green slice root-anchored private-output ignore rules and placed the
  previously ignored `captures` production package under version control.
- Focused capture/event/runtime/package tests passed, and `./scripts/verify-host.sh` exited 0 with
  369 tests passed in 28.69 seconds and 85.26% coverage; Ruff, formatting, strict mypy, protocol
  examples, secret scan, dependency audit and offline doctor were Green. The temporary diagnostic
  harness independently passes 10 tests, Ruff, strict mypy and format checks. No Firmware source
  changed in `517011a`, so no further flash is required before the next diagnostic. After adding
  the evidence contract, the final host gate remained Green with 370 tests passed in 29.20 seconds
  and the same 85.26% coverage.
- A second separately consented request sent exactly one camera command through the same bounded,
  nonpersistent production Control/Gateway harness, with no retry. It returned HTTP 504
  `CAPTURE_TIMEOUT` after 45,227 ms at stage `device_reconnected_or_disconnected`; the original
  authenticated connection changed or disconnected during device-side processing. Safe aggregate
  evidence was `capture_completed_events=0`, zero capture/upload and failure metrics, zero
  queue/device/input/touch events, and `connection_stable=false`. Thus no Firmware completion event
  or Gateway upload was observed.
- No image was displayed, viewed, externally processed or retained. The run emitted no image bytes,
  exact image hash or capture identifier, left zero owned capture media/temporary capture
  directories, and ended with one idle serial device, no Bridge/listener on 8765/8766 and the one
  approved firewall rule still retained for final Goal cleanup.
- Static follow-up found that the one `std::thread` performing capture, JPEG conversion and HTTP
  upload inherited ESP-IDF's 3,072-byte default pthread stack. This is consistent with the observed
  device connection change, but the run had no simultaneous serial trace and does not prove stack exhaustion.
  A failing Firmware contract test preceded commit `f6f0d2d`, which gives only the
  camera worker a 12 KiB stack, restores the calling task's pthread configuration and fails closed
  if the scoped configuration cannot be applied; it does not raise the global thread default.
- The source gate for `f6f0d2d` passed 371 host tests at 85.20% coverage, all 20 Firmware CTests,
  dependency/source verification and a clean ESP-IDF build. The temporary verification image was
  3,919,712 bytes with 24% app-partition headroom and SHA-256
  `31a000e291428d17b746b07747ae7858e89c6ab026b7ba1c3075dff4f04dd581`; it was gate-only and was
  deleted automatically, so it is not a retained flash candidate.
- A retained candidate was then built from source commit `64062cd`, containing scoped-stack
  implementation `f6f0d2d`, at
  `firmware/build-hermes-hw12-stack-64062cd/stack-chan.bin`. It is 3,919,712 bytes with SHA-256
  `f984c5181a48a3cf86a97f9cac59c0584d7c4eeb8a4ad8b81226c972f0cf92a6`, 24% app-partition
  headroom, and valid image checksum/validation hash. Its generated configuration keeps the Bridge,
  primary USB console, provisioning and head-motion lock enabled, leaves coredumps disabled, and
  its partition table is byte-identical to both the factory backup and flashed predecessor. The
  app-only arguments contain only `0x20000 stack-chan.bin` after the flash settings.
- Immediately before writing, one idle stable serial identity, the 16 MiB factory backup and its
  partition digests, unchanged Secure Boot-disabled/`SPI_BOOT_CRYPT_CNT=0` state, the current
  predecessor app digest, candidate hash/config/partition, zero listeners and the one exact scoped
  firewall rule all revalidated. After separate explicit approval, esptool wrote only the
  3,919,712-byte app at `0x20000` in 21.0 seconds and verified its write hash. Bootloader, partition
  table, NVS and assets were untouched. A separate independent read-only digest then matched the
  retained candidate.
- Two content-suppressed monitor setup windows were rejected as boot evidence: the first failed to
  produce a deliberate reset, while the second contained two complete clean boot marker sets because
  monitor's automatic reset was followed by a manual reset. Neither was a Firmware failure. The
  accepted `--no-reset` monitor window sent exactly one manual reset and collected 16,037 bytes:
  exactly one ROM, reset, `stack-chan` project and Firmware `1.5.1` marker, with zero
  panic/watchdog/assert markers. No raw serial content was displayed or retained, and the port was
  released afterward.
- Postflight found one idle serial identity, no monitor/Bridge/listener, no owned capture temporary
  directory, USB still attached and exactly one enabled scoped firewall rule retained for final
  Goal cleanup. No camera command was sent during build, flash, digest or boot verification.
- One fresh approval was consumed by one post-stack diagnostic; the operator's multi-count wording
  was not retained as approval for future attempts. The attended harness sent exactly one camera
  command and made no automatic retry. It returned HTTP 504 `CAPTURE_TIMEOUT` after 45,091 ms at
  `device_reconnected_or_disconnected`, with `capture_completed_events=0`,
  `connection_stable=false`, zero capture/upload and failure metrics, and no queue, device, input or
  touch event. No Firmware completion event or Gateway upload was observed.
- No image was displayed, viewed, externally processed or retained. No image bytes, exact hash or
  capture identifier were emitted. Postflight found zero owned capture media, no capture temporary
  directory, no Bridge/listener on 8765/8766, one free serial identity, USB still attached and the
  one scoped firewall rule intact.
- The 12 KiB mitigation did not resolve the physical failure: the terminal stage was unchanged from
  the pre-mitigation request. This does not establish whether the remaining cause is another stack
  constraint, camera/driver behavior, power/reset behavior or HTTP processing because neither run
  had a simultaneous serial trace. HW-12 remains NOT RUN because no valid physical capture/upload
  lifecycle completed. Do not repeat the unchanged request; add bounded cause-discriminating
  diagnostics before requesting fresh explicit camera consent for any further camera command.
- The evidence update's complete `./scripts/verify-host.sh` gate was Green with 374 tests passed in
  28.12 seconds at 85.20% branch coverage; formatting, Ruff, strict mypy, protocol validation,
  secret scan, dependency audit and offline doctor also passed.
- A new fresh approval authorized one content-free serial diagnostic. The attended production
  harness sent exactly one camera command with no automatic retry and returned HTTP 504
  `CAPTURE_TIMEOUT` after 45,016 ms at `device_reconnected_or_disconnected`; Firmware completion,
  capture and upload counts remained zero.
- The read-only serial observer discarded 13,948 bytes without printing or retaining them. Its
  aggregate evidence was `serial_panic_markers=2`, `serial_boot_markers=1`,
  `serial_reset_markers=1`, `serial_camera_frame_markers=0`,
  `serial_camera_error_markers=0`, `serial_brownout_markers=0`,
  `serial_watchdog_markers=0`, `serial_stack_markers=0`, `serial_heap_markers=0`, and zero serial
  disconnect/reopen events. The two panic-marker matches can come from different words in one panic
  report and do not establish two crashes; the single boot/reset pair establishes one reset window.
- This `panic_observed` result is consistent with a panic before the existing frame-copy marker,
  but the intentionally content-free aggregation does not identify the exact panic site. It does
  not establish which operation between worker entry and frame copy failed. No image was displayed, viewed, externally processed or retained.
  No image identifier, image hash or raw serial was exposed, and postflight found zero owned capture media,
  one free serial identity, no WSL/Windows listener, USB attached and the one scoped rule intact.
  HW-12 remains NOT RUN; a failing stage-boundary test and the smallest diagnostic or correction
  must precede any further physical camera request.
- The content-free serial evidence update's complete host gate was Green with 375 tests passed in
  28.01 seconds at 85.20% branch coverage; formatting, Ruff, strict mypy, protocol validation,
  secret scan, dependency audit and offline doctor also passed.
- A further fresh approval authorized one content-free backtrace diagnostic after its temporary
  harness passed 36 tests, Ruff and strict mypy. The attended production harness sent exactly one
  camera command with no automatic retry and returned HTTP 504 `CAPTURE_TIMEOUT` after 45,020 ms at
  `device_reconnected_or_disconnected`; completion, capture, upload, input and touch counts were all
  zero.
- The observer immediately discarded 13,726 serial bytes. Its bounded evidence was
  `serial_backtrace_addresses=9`, `serial_panic_markers=2`, `serial_boot_markers=1`,
  `serial_reset_markers=1`, `serial_camera_frame_markers=0`,
  `serial_camera_error_markers=0`, with zero brownout, watchdog, stack, heap, serial disconnect and
  reopen markers. The boot/reset pair bounds one observed reset window; the two panic-word matches
  do not establish two crashes.
- Retained-ELF symbolization classified the nine bounded code addresses as
  `shutter_audio_path`. With the static call order and absent frame-copy marker, the backtrace
  narrows the observed panic to shutter-sound playback before camera dequeue/frame copy, but the
  content-free classification does not identify the exact faulting instruction. It exposed or
  retained no exact addresses, raw symbols or raw serial. No image was displayed, viewed, externally processed or retained.
  Postflight found zero owned capture media, one free serial identity, no WSL/Windows listener, USB
  attached and the one approved scoped firewall rule intact. HW-12 remains NOT RUN pending a
  failing shutter-audio boundary test and the smallest correction before another newly consented
  physical camera request.
- The content-free backtrace evidence update's complete host gate was Green with 376 tests passed in
  30.29 seconds at 85.26% branch coverage; formatting, Ruff, strict mypy, protocol validation,
  secret scan, dependency audit and offline doctor also passed.
- A failing Firmware contract preceded the main-task shutter-audio correction in `8ad0489`.
  `StackChanCamera::Capture` now schedules the shutter sound onto `Application::Schedule` instead of
  executing the codec/timer/Ogg path on the 12 KiB camera pthread. Final `./scripts/verify.sh` was
  Green with 377 tests passed in 30.88 seconds at 85.26% branch coverage, all 20 Firmware CTests, source/dependency
  checks and a fresh ESP-IDF build. Its temporary 3,919,968-byte image, SHA-256
  `feda68eb9e682cfafdb9997682addf079fda9617ee860f3fffb9a814b573ad1e`, was removed and not flashed.
- The retained candidate is
  `firmware/build-hermes-hw12-shutter-8ad0489/stack-chan.bin`, 3,919,968 bytes, SHA-256
  `8b55b48a84e71820456dee68d16a2e73a7eb5ab836a8a3e8bd0638fe4686e296`. Its checksum and validation
  hash are valid, 24% of the app partition is free, its generated configuration retains Bridge,
  primary USB console, provisioning and head-motion lock with coredumps disabled, and its partition
  table matches the factory and predecessor. The app mapping is `0x20000`-only.
- A fail-closed preflight revalidated one free device, backup and partition hashes, unchanged
  security state, predecessor digest, candidate configuration, zero listeners and one exact scoped
  firewall rule. After separate explicit approval, esptool wrote only the 3,919,968-byte app and
  verified its write hash; bootloader, partition, NVS and assets were untouched. An independent
  read-only digest then matched the retained candidate.
- A physical-button observation was rejected when USB detached before boot markers were captured.
  The first same-FD serial hard-reset window saw one transient FreeRTOS stack-overflow followed by
  one automatic reboot. It did not reproduce in three consecutive clean boot windows: each accepted
  35-second window had exactly one ROM/reset/project/version marker and zero stack, panic, watchdog,
  assert, heap, brownout or disconnect markers. The transient remains unexplained and is not evidence
  of a permanent correction. Raw serial was immediately discarded and never displayed or retained.
  There was no camera command during the prerequisite work. No image was displayed, viewed, externally processed or retained.
  Postflight found one free serial device, USB attached, no WSL/Windows listener or capture media,
  and the approved scoped firewall rule intact. HW-12 remains NOT RUN; one content-suppressed retry
  still requires fresh explicit camera consent.
- The main-task shutter-audio flash evidence host gate was Green with 378 tests passed in 31.48 seconds
  at 85.26% branch coverage; formatting, Ruff, strict mypy, protocol validation, secret scan,
  dependency audit and offline doctor also passed.

## Successful physical camera acceptance

- The successful post-correction HW-12 capture used the retained `8ad0489` app after a fresh explicit
  privacy approval. The harness sent exactly one camera command with no automatic retry. The device
  remained authenticated with camera capability present and remote head capability false.
- The authenticated lifecycle completed with HTTP `201` / `200` / `404` for reservation, fetch and
  post-expiry fetch. `capture_completed_events=1`, `capture_completed_ok=1`, `capture_total=1.0`,
  `capture_failure_total=0.0`, `local_capture_green=true` and `machine_valid=true`. Completion
  ownership and response metadata agreed without recording the capture identifier.
- The uploaded 4,948-byte payload had valid JPEG boundaries and decoded dimensions of 320 x 240.
  Its temporary store used directory mode `0700` and file mode `0600`; TTL purge removed one record,
  leaving `files_remaining=0`, and the temporary directory was removed. No image hash was recorded.
- The connection stayed stable and the device returned to IDLE with zero input, touch, queue and
  device-error events. The content-suppressed serial observer discarded 227 serial bytes and saw
  `serial_camera_frame_markers=1`, `serial_camera_error_markers=0`, and zero panic, watchdog, stack, heap, brownout, reset and disconnect markers.
- The operator watched and listened throughout but reported that the shutter sound was not heard and
  no screen change was seen. Those observations remain presentation follow-ups and are not recast as
  successful audiovisual feedback. No image was displayed, viewed, externally processed or retained.
- Postflight found one free serial device, USB attached, no listener on 8765/8766, no owned capture
  media or capture directory, and the single scoped firewall rule retained until final Goal cleanup.
  HW-12 physical capture/upload is PASS. At that checkpoint live Hermes `input_image` remained a
  separate CAM-002 result; the later accepted vision turn completed it.
- The HW-12 acceptance evidence host gate was Green with 379 tests passed in 31.94 seconds at 85.20%
  branch coverage; format, Ruff, strict mypy, protocol validation, secret scan, dependency audit and
  offline doctor were also Green.

## HW-13 wrong-token rejection and recovery

- The successful HW-13 wrong-token recovery used a TDD-built temporary harness whose nine tests,
  Ruff, format and strict mypy checks were Green. It first established an authenticated IDLE
  baseline, then used exactly one wrong-token phase before restoring the correct Bridge expectation.
  The device was provisioned only with the correct process-generated token.
- In the accepted repeat, the wrong Bridge recorded `wrong_auth_failures=5.0` while
  `wrong_phase_registered=false`. After the correct Bridge returned, the same model/Firmware with
  `head=false` registered, `recovery_elapsed_ms=26890`, and `final_state_idle=true` after
  `status_commands=2`. It sent no camera, audio or actuator command.
- The observer discarded 1,066 serial bytes and recorded zero boot, panic, watchdog, stack, heap, brownout and reset markers;
  serial disconnect/reopen counts were also zero. There were zero input, touch, queue and device-error events.
- The first attended run supplied the explicit wrong-token display observation: the operator saw
  `Connecting Bridge` and no other change, but missed the recovery display. A separately approved
  repeat then supplied the recovery observation: `Bridge connected` was visible, and the operator
  confirmed no contact with the device, desk or cable. Neither repeat was automatic.
- No token or raw serial was displayed or retained in host evidence. Postflight found one free
  serial device, USB attached, no listener on 8765/8766, no harness process, and the scoped firewall rule retained
  until final Goal cleanup. The wrong-token slice is Green; at that checkpoint, HW-13 was PARTIAL
  pending Hermes-stop, TTS-stop, temporary Wi-Fi-loss and camera-failure evidence.
- The HW-13 evidence host gate was Green with 380 tests passed in 32.06 seconds at 85.26% branch coverage;
  formatting, Ruff, strict mypy, protocol validation, secret scanning, dependency audit and offline
  doctor were Green.

## HW-13 Hermes stop and recovery

- The successful HW-13 Hermes-stop recovery used local Mock Hermes through the production public HTTP/SSE client,
  plus the production Gateway, voice-turn service, failure notifier and audio
  streamer. It stopped the Mock Hermes process exactly once after a ready authenticated baseline.
  The failure path reported `failure_error_code=HERMES_FAILED`,
  `failure_notification_successes=1`, `failure_audio_frames=0.0` and
  `failure_turn_released=true`, then returned the device to IDLE without failure audio.
- The first explicitly approved diagnostic displayed a blank Japanese toast because the physical
  toast uses `lv_font_montserrat_20`, which does not contain the selected Japanese glyphs. Its
  machine-complete but inaudible 440 Hz recovery was also rejected as operator evidence. Failing
  tests preceded the minimal ASCII notification mapping and 880 Hz harness correction; the
  separately approved accepted run was not an automatic retry.
- In the accepted run the operator clearly read `HERMES OFFLINE`. The recovery probe then recorded
  `recovery_probe_ready=true`, `recovery_turn_completed=true`, `recovery_output_streams=1`,
  `recovery_audio_frames=20.0`, `recovery_elapsed_ms=35` and `recovery_device_idle=true`.
  The operator heard one 880 Hz recovery tone, saw no other screen change and confirmed no physical contact
  with the device, desk or cable. There was no camera, microphone or actuator command and
  only one bounded recovery audio stream.
- The content-suppressed observer discarded 1,412 serial bytes and recorded zero input, touch,
  queue and device-error events, plus zero boot, panic, watchdog, stack, heap, brownout and reset
  markers. Postflight found no listener or harness process and Windows still reported USB attached
  with the scoped firewall rule retained; WSL serial enumeration was absent despite that Windows
  attachment state and is recorded as a follow-up before another physical run.
- This local Mock Hermes result validates failure/recovery through the production public HTTP/SSE
  client only; live HW-09 remains NOT RUN. The Hermes-stop slice is Green; at that checkpoint,
  HW-13 was PARTIAL pending TTS-stop, temporary Wi-Fi-loss and camera-failure evidence.
- The HW-13 Hermes-stop evidence host gate was Green with 389 tests passed in 31.83 seconds at
  85.26% branch coverage; formatting, Ruff, strict mypy, protocol validation, secret scanning,
  dependency audit and offline doctor were Green.

## HW-13 TTS stop and recovery

- The successful HW-13 TTS-stop recovery used a 13-test temporary harness with Ruff, format and
  strict mypy Green. It kept local Mock Hermes available and exercised a local HTTP WAV provider
  through the production TTS adapter `GenericHttpWavTtsAdapter`, production Gateway, voice-turn,
  failure-notification and audio-streaming paths.
- After an authenticated ready baseline with `tts_baseline_ready=true`, the attended run used one TTS stop phase
  and no automatic retry. Stopping only the provider produced `failure_error_code=TTS_FAILED`,
  `failure_notification_successes=1`, `failure_audio_frames=0.0` and `failure_turn_released=true`;
  the device remained connected and returned to IDLE without failure audio.
- The operator clearly read `TTS OFFLINE`, reported no abnormal screen change and confirmed no physical contact.
  After a fresh provider returned, machine evidence recorded `tts_stop_phases=1`,
  `recovery_tts_ready=true`, `recovery_turn_completed=true`, `recovery_output_streams=1`,
  `recovery_audio_frames=20.0`, `recovery_elapsed_ms=35` and `recovery_device_idle=true`.
  The operator heard one 880 Hz recovery tone. There was no camera, physical microphone or actuator command
  and only one bounded recovery audio stream.
- The content-suppressed observer discarded 23,728 serial bytes with zero input, touch, queue and device-error events
  and zero boot, panic, watchdog, stack, heap, brownout and reset markers. Postflight found one free serial device,
  USB attached, no listener on 8765/8766/18767/18768, no harness process and the scoped firewall rule retained.
- This validates local failure/recovery through the production TTS adapter. At that TTS-stop
  checkpoint, live HW-10 was NOT RUN and HW-13 was PARTIAL pending temporary Wi-Fi-loss and
  camera-failure evidence.
- The HW-13 TTS-stop evidence host gate was Green with 390 tests passed in 33.34 seconds at
  85.26% branch coverage; formatting, Ruff, strict mypy, protocol validation, secret scanning,
  dependency audit and offline doctor were Green.

## HW-13 camera failure and recovery

- The successful HW-13 camera-failure recovery used a 21-test temporary harness whose pytest,
  Ruff, format and strict mypy checks were Green. Fresh explicit privacy approval covered exactly
  one camera command and no host-side retry. The production `CaptureCoordinator`, `CaptureStore`,
  Device Gateway and Control API were used; only the Gateway upload route was deliberately supplied
  `capture_store=None`, which the harness contract proved rejects an authenticated upload before
  request form/body parsing.
- The single physical command reached `serial_camera_frame_markers=1`. Its built-in three bounded
  Firmware upload attempts were all rejected as unavailable, yielding
  `capture_store_unavailable_responses=3`. Firmware then emitted one owned failure with
  `capture_completed_events=1`, `capture_completed_ok=0` and `failure_event_forwarded=true`.
  Control returned `control_status=409` and `control_error_code=CAPTURE_FAILED` after
  `elapsed_ms=505`.
- The reservation lifecycle closed with `reservations=1` and `reservation_cancels=1`.
  `capture_total=0.0`, `files_remaining=0` and `temporary_directory_removed=true`; the host did not
  inspect the media, and no raw image bytes, exact image hash or capture ID were displayed or retained,
  and the image was not viewed, displayed, externally processed or stored.
- The stable authenticated connection completed `status_commands=2` and
  `final_state_idle=true`, with no audio or actuator command. The content-suppressed observer
  discarded 2,924 serial bytes and recorded zero input, touch, queue and device-error events plus
  zero camera-error, boot, panic, watchdog, stack, heap, brownout and reset markers. The operator
  reported no shutter sound and no physical contact; screen presentation was not observed, so this
  result makes no physical display claim.
- Postflight found one free serial device, USB attached, no listener on 8765/8766/18767/18768, no
  harness process and the scoped firewall rule retained for final Goal cleanup. The camera-failure
  transport, owned error and IDLE recovery path is machine Green. At that camera-failure
  checkpoint, HW-13 was PARTIAL solely because temporary Wi-Fi loss was NOT RUN.
- The HW-13 camera-failure evidence host gate was Green with 391 tests passed in 34.60 seconds at
  85.26% branch coverage; formatting, Ruff, strict mypy, protocol validation, secret scanning,
  dependency audit and offline doctor were Green.

## HW-13 Wi-Fi loss and recovery

- The successful HW-13 Wi-Fi-loss recovery used a 19-test temporary harness whose pytest, Ruff,
  format and strict mypy checks were Green. Source commit `3f3ee40` added a compile-time-disabled,
  one-shot USB diagnostic. The reviewed diagnostic image was 3,921,040 bytes with SHA-256
  `137d140de9f4279c86654949307003dfb6d216648e923cc84130057cd1acf4f3`, retained the physical
  head-motion lock and was written only at `0x20000`; its esptool write hash, independent read-only
  digest and clean 30-second boot passed.
- From an authenticated K151, Wi-Fi-connected IDLE baseline, the attended run sent
  `wifi_cycle_commands=1` with `cycle_duration_seconds=15`. The USB console returned
  `cycle_start_acks=1` and `cycle_restart_acks=1`. The production Device Gateway observed
  `websocket_disconnects=1.0`, then `recovery_connection_replaced=true` after
  `recovery_elapsed_ms=11329`; final checks returned `recovery_idle=true` and
  `recovery_wifi_connected=true`.
- There was no camera, audio or actuator command. The content-suppressed observer discarded
  1,286 serial bytes and recorded zero input, touch, queue and device-error events plus zero boot,
  panic, watchdog, stack, heap, brownout and reset markers. The operator saw both
  `Connecting Bridge` and `Bridge connected`, reported no abnormal movement or sound and confirmed
  no physical contact.
- After the bounded result, the 3,920,800-byte motion-locked normal release from source commit
  `3f3ee40`, SHA-256
  `32988d0d66eea2a44e690c1b593182b411f1b1408c23eeb2d0aa59a59aca7e71`, was written only at
  `0x20000`. Its esptool write hash, independent read-only digest and clean 30-second boot passed;
  the diagnostic feature disabled state is now restored. Bootloader, partition table, NVS,
  Wi-Fi credentials and assets were not rewritten. Together with the earlier wrong-token,
  Hermes-stop, TTS-stop and camera-failure evidence, HW-13 is PASS.
- The HW-13 Wi-Fi-loss evidence host gate was Green with 429 tests passed in 33.69 seconds at
  85.32% branch coverage; formatting, Ruff, strict mypy, protocol validation, secret scanning,
  dependency audit and offline doctor were Green.

## Scenario results

The previously flashed attended-motion candidate is retained from commit `8384214` as
`firmware/build-hermes-motion-8384214/stack-chan.bin`: 3,921,232 bytes, SHA-256
`af98e32ce32aa21214d4c8e29440fb2785b1f2f020f405ae2e049a332ebd7d7d`, 24% app-partition
headroom, valid checksum/validation hash, factory-identical partition table and a single app-only
`0x20000` argument. Its generated config disables the global output lock only while enabling
`CONFIG_STACKCHAN_HERMES_LOCAL_MOTION_LOCK=y`, so local/avatar/IMU/BLE/app motion is rejected and
only bounded authenticated Bridge head commands are eligible. The normal release motion lock remains enabled
by default. This candidate supplied the completed HW-04 evidence, but after the HW-13 Wi-Fi diagnostic
the current physical device was restored to the motion-locked normal `3f3ee40` image listed above. Its
authenticated `head=true` capability and one initial bounded command have now been physically checked.
Flash and attended motion require distinct explicit approvals.

The 2026-09-03 attended motion-candidate preflight passed with exactly one free stable serial
identity. The private 16 MiB factory backup, both SHA sidecars and mode `0700`/`0600` protections
revalidated; the retained candidate remained 3,921,232 bytes with its recorded SHA-256, valid
checksum and validation hash, factory-identical partition table, required Bridge/USB/local-lock
configuration and a single `0x20000` app entry. The current motion-locked app digest matched the
retained `8ad0489` image. Secure Boot and Flash Encryption remained disabled. The one exact
WSL/LocalSubnet/TCP-8765 rule and default inbound Block remained in force, with no Windows or WSL
listener on 8765/8766. Esptool issued a final hard reset for normal boot; no post-reset boot
qualification is claimed at this preflight checkpoint. There was no flash write or physical head
command; explicit flash approval remains pending and cannot authorize later motion.

The 2026-09-03 attended motion-candidate app-only flash then ran under the user's distinct explicit
flash approval. It revalidated exactly one free stable serial, the verified factory backup,
factory-identical partition, disabled Secure Boot/Flash Encryption and the locked predecessor's
digest before writing only the 3,921,232-byte candidate at `0x20000`. The esptool write hash and
independent digest both matched. A 35.09-second content-suppressed boot window discarded
11,874 serial bytes and counted one boot marker, one Firmware-version marker and two reset markers,
with zero panic, watchdog, stack, heap, brownout, camera-error, serial-disconnect or reopen markers.
Postflight again found one free stable serial, no Windows/WSL listener and the exact scoped firewall
rule retained. No Bridge session or actuator command followed: no physical head command has been
sent, and physical motion approval remains pending as a second distinct approval.

The 2026-09-03 attended initial K151 motion followed a fresh, distinct physical-motion approval.
Before touching the device, a new failing test exposed that the smoke helper accepted an
HTTP-success/device-`ok=false` result; commit `c033aff` makes that path fail closed, and its focused
5/5 tests plus the 418-test host gate were Green. The content-suppressed live harness was developed
Red→Green with 12/12 tests, formatting, Ruff and strict mypy Green, then removed after use. Its
preflight reverified exactly one free stable serial, the factory backup and current candidate digest;
the exact Hyper-V Inbound/Allow/TCP-8765/LocalSubnet rule remained the only rule, the WSL VM default
inbound action was Block and Windows/WSL listeners were zero. A process-only token authenticated the
same `M5STACK-K151` on Firmware `1.5.1` with `head=true` and initial IDLE. The harness released
exactly one `head.set_angles` command with `yaw=5`, `pitch=45`, `speed=10`; it sent no retry,
follow-up or home command. The device acknowledged it, `motion_commands=1`, the connection stayed
stable and final state was IDLE after a 4,507 ms command/observation window. The observer discarded
143 serial bytes and counted zero device/servo, queue, input, touch, boot, reset, panic, watchdog,
stack, heap, brownout, camera-error, disconnect or reopen markers. The operator observed motion,
reported no abnormal sound, vibration or heat, and touched neither the device, desk nor cable.
Postflight found one free stable serial and zero listeners/harness processes; the scoped firewall
rule remains for final Goal cleanup. The physical yaw/pitch/home sequence remains incomplete because
this observation does not establish direction-specific yaw or pitch behavior, or `head.home`.

The 2026-09-03 attended K151 home attempt followed another distinct approval. A home-only live
harness was developed Red→Green with 15/15 tests, formatting, Ruff and strict mypy Green. Preflight
reverified the one free stable serial, verified factory backup, retained candidate digest, exact
Hyper-V Inbound/Allow/TCP-8765/LocalSubnet rule, default inbound Block and zero Windows/WSL
listeners. It released exactly one `head.home` command, with no retry or additional motion command.
The device acknowledged it with `motion_commands=1`, `home_commands=1`, `angle_commands=0`; the
connection remained stable and final state was IDLE after a 4,450 ms command/observation window.
The observer discarded 1,291 serial bytes and counted zero device/servo, queue, touch, boot, reset,
panic, watchdog, stack, heap, brownout, camera-error, disconnect or reopen markers. It nevertheless
counted `input_starts=1`, `input_frames=41`, `input_ends=1`, so the fail-closed classifier returned
`machine_valid=false`. The operator said the head appeared already centered and did not observe
movement, reported no abnormal sound, vibration or heat, and touched neither the device, desk nor
cable. The unexplained no-contact input lifecycle is retained without a causal claim. Successful
command acknowledgement is not treated as physical position feedback; physical home remains
unestablished. Postflight found one free serial and zero listeners/harness processes. The scoped
firewall rule remains for final Goal cleanup.

The 2026-09-03 attended K151 positive-yaw observation followed a new distinct approval. A yaw-only
live harness was developed Red→Green with 20/20 tests, formatting, Ruff and strict mypy Green; the
existing smoke helper was also 8/8 Green. Preflight reverified one free stable serial, the factory
backup, retained candidate digest, exact scoped Hyper-V rule/default inbound Block, zero listeners,
the exact `M5STACK-K151`/Firmware `1.5.1`/`head=true` identity, initial IDLE and zero pre-command
audio, event or serial activity. It released exactly one `head.set_angles` command with `yaw=10`,
`pitch=45`, `speed=10`; there was no retry or home command. The device acknowledged the exact
arguments with `motion_commands=1`, `angle_commands=1`, `home_commands=0` and
`exact_yaw_commands=1`. The connection remained stable and final state was IDLE after a 4,474 ms
window. The observer discarded 337 serial bytes; `input_starts=0`, `input_frames=0`, `input_ends=0`
and all device/servo, queue, touch, boot, reset, panic, watchdog, stack, heap, brownout,
camera-error, disconnect and reopen counts were zero. The classifier returned `machine_valid=true`.
The operator observed the face move slightly to the left when viewed from the front, reported no
abnormal sound, vibration or heat, and touched neither the device, desk nor cable. Postflight found
one free serial and zero Windows/WSL listeners or harnesses. The positive yaw direction is
physically established; pitch and home remain unestablished. No return-home command was inferred
from this approval, and the scoped firewall rule remains for final Goal cleanup.

The 2026-09-03 attended K151 return-home observation used the already verified positive-yaw offset
and a further distinct approval. The temporary return-home harness reached 52/52 Red→Green tests,
with formatting, Ruff and strict mypy Green. Its first exact-float position check safely rejected the
quantized servo readback; a tested ±2-degree bound then accepted only the intended offset and home
neighborhoods. In this sequence, all preceding starts stopped before a motion command. After exact
identity, capability, IDLE, position, audio, event and serial guards passed, the final armed run released
exactly one `head.home` command. The operator observed a rightward return to center, confirmed the
head was centered, reported no abnormality, and touched neither the device, desk nor cable. The
result collector subsequently ended with `unexpected_error` and `machine_valid=false`, so command
acknowledgement, complete counters and connection/fault evidence are not claimed. A separate
stdin-closed read-only run could not reach the motion path and returned `position_home=true`,
`position_offset=false`. Accordingly, physical return-to-home motion was observed, but
machine-valid home completion remains unestablished. Postflight found exactly one serial device,
zero Windows/WSL listeners and no harness process. The one enabled Hyper-V rule remained limited to
the WSL creator, inbound Allow, TCP 8765 and `LocalSubnet`, with default inbound Block, for final Goal
cleanup.

The 2026-09-03 attended K151 pitch observation followed a new distinct approval from the
read-only-confirmed home position. The pitch-only live harness was developed Red→Green with 61/61
tests, formatting, Ruff and strict mypy Green; the existing hardware-smoke helper was also 8/8
Green. Preflight reverified one serial device, zero WSL/Windows listeners and harnesses, the exact
scoped Hyper-V rule with default inbound Block, the verified factory backup and candidate digest,
the exact K151/Firmware `1.5.1`/`head=true` identity, IDLE, bounded home readback and zero
audio/event/serial activity. It released exactly one `head.set_angles` command with `yaw=0`,
`pitch=40`, `speed=10`; there was no retry or home command. The device acknowledged the exact
arguments with `machine_valid=true`, `motion_commands=1`, `angle_commands=1`, `home_commands=0` and
`exact_pitch_commands=1`. Three physical readbacks covered `initial_pitch=45.3`,
`final_pitch=40.3` and the unchanged pre-command home position; yaw remained 0.6 degrees. The
connection stayed stable and final state was IDLE after 4,839 ms. The content-free observer
discarded 143 serial bytes;
`input_starts=0`, `input_frames=0`, `input_ends=0`, backtrace addresses were zero, and all
device/servo, queue, touch, boot, reset, panic, watchdog, stack, heap, brownout, camera-error,
disconnect and reopen counters were zero. The operator observed the head move downward when viewed
from the front, reported no abnormal sound, vibration or heat, and touched neither the device, desk
nor cable. Postflight found one serial, zero Windows/WSL listeners and no harness; the one scoped
rule remains for final Goal cleanup. The decreasing pitch direction is physically established;
machine-valid home completion remains unestablished, and HW-04 stays PARTIAL.

The 2026-09-03 attended K151 machine-valid home followed a new distinct approval from that measured
pitch offset. The home-only live harness was developed Red→Green with 57/57 tests, formatting, Ruff
and strict mypy Green; the existing hardware-smoke helper was also 8/8 Green. Preflight reverified
one serial device, the factory backup, retained candidate digest, exact scoped Hyper-V rule/default
inbound Block, zero Windows/WSL listeners and harnesses, the exact K151/Firmware
`1.5.1`/`head=true` identity, IDLE, bounded `yaw=0`/`pitch=40` readback and quiet
audio/event/serial gates. It released exactly one `head.home` command, with no retry or additional
motion command. The result was `machine_valid=true`: `motion_commands=1`, `home_commands=1`,
`angle_commands=0`, `exact_home_commands=1`, command acknowledgement, stable connection and final
IDLE. Its `position_reads=3` covered initial, immediate-pre-command and final positions;
`initial_pitch=40.3`, `final_pitch=44.3`, and `final_yaw=0.6`, placing the final readback within the
configured ±2-degree home neighborhood around 0/45. The 4,497 ms window discarded 277 serial bytes;
`input_starts=0`, `input_frames=0`, `input_ends=0`, and all device/servo, queue, touch, boot, reset,
panic, watchdog, stack, heap, brownout, camera-error, disconnect, reopen and backtrace counts were
zero. The operator observed one upward movement when viewed from the front, reported no abnormal
sound, vibration or heat, and touched neither the device, desk nor cable. The operator did not
independently judge the fine final angle by eye and saw no second movement; the single upward move
was the expected home action, while the bounded readback supplies the position evidence. Postflight
found one serial, zero Windows/WSL listeners and harnesses, a clean worktree before these evidence
edits, the exact one scoped rule and default inbound Block. Thus machine-valid home completion is
established. Existing yaw, pitch, expression, LED, brightness and volume evidence now completes
HW-04 without changing the conservative release lock or the historical failed-closed results.

## Live HW-09 Hermes Responses API

HW-09 live Hermes Responses API is PASS. On 2026-09-03, the Bridge reached Hermes Agent v0.20.0
on a private local host only through authenticated SSH forwarding to its loopback-bound port 8642.
`GET /health` returned `status=ok`. The authenticated current capability document advertised the
Responses/SSE, `X-Hermes-Session-Key`, Skills and toolsets surfaces, but used nested `features` and
`endpoints` plus a singular `model`. A failing compatibility test preceded the minimal normalizer
in commit `8cb295e`; both the legacy flat contract and current nested contract then passed. The live
Bridge readiness result was fully Green, including model, streaming, session key, inline-image API
surface, `/v1/skills` and `/v1/toolsets` discovery.

Three independent named-device Responses/SSE turns completed through the production client:

- `こんにちは`: **2,721 ms**, completed normally with a Japanese greeting.
- `今日の日付を教えて`: **5,665 ms**, returned the correct `2026年9月3日、木曜日` and completed
  two `terminal` tool calls.
- An explicit `ascii-art` Skill request: **8,590 ms**, returned the requested StackChan art, invoked
  `skill_view` twice and exposed the requested Skill reference in structured tool events.

Each stream contained `response.created`, text deltas and `response.completed`. The remote API key
was transferred only into a short-lived process environment through the authenticated SSH control
connection; it was never printed, written to the repository or committed. This is text/Skill
evidence only: it does not complete HW-10 physical full voice or CAM-002 live image.

## Live HW-08 local STT

HW-08 live local faster-whisper STT is PASS. On 2026-09-03, the production
`FasterWhisperSttAdapter` loaded the locked `small` model on CPU/INT8. The input came from the
pre-existing macOS `Kyoko` Japanese voice over the authenticated SSH control connection and was
decoded as 16 kHz mono PCM. Every AIFF existed only in a freshly created remote temporary directory,
was streamed into the process and removed by an EXIT trap; normalized samples were process-only and
no audio retained.

- `こんにちは` → `こんにちは`: **3,689 ms** (first call includes model startup), 0.796 s audio.
- `今日の日付を教えて` → `今日の日付を教えて`: **2,150 ms**, 1.713 s audio.
- `スタックチャン、元気ですか` → `スタックちゃん、元気ですか?`: **2,238 ms**, 1.889 s
  audio; the kana and punctuation differences are semantically equivalent.
- One second of all-zero PCM: **10,961 ms**; empty speech returned an empty result.

All four results reported Japanese with language probability 1.0. That field is language detection
probability, not transcription confidence. This completes the live/local provider boundary only;
the physical touch→microphone→Hermes→TTS→speaker boundary was accepted in the following run.

## Live physical HW-10 full voice

HW-10 live physical full voice turn is PASS. An initial separately consented live run after the
audio-tail correction captured 112 input frames and sent 121 output frames. It reached one STT and
one Hermes request plus two TTS segments, and the operator heard and understood the answer without
additional contact. However, one physical contact produced two turn outcomes (`turn.failed` then
`turn.completed`) and five playback underruns. This historical duplicate-turn and underrun finding
was rejected as final HW-10 evidence.

Failing tests then reproduced both defects. Firmware commit `9f42b92` disarms the head-touch
debouncer after a stable release until stable idle is observed, preventing release bounce from
becoming a second press. Bridge commit `f73ff28` paces Opus output against absolute monotonic
deadlines so encoding and WebSocket send delay no longer accumulate on top of every frame period.
The full `./scripts/verify.sh` gate passed with 436 host tests, 85.45% coverage, 22/22 Firmware
CTest and a fresh ESP-IDF build. The retained motion-locked image is
`firmware/build-hermes-hw10-final-f73ff28/stack-chan.bin`, 3,920,864 bytes, SHA-256
`41cd8affc309006f7fc1adaaeafe5f50cf1b1bc2e4daf1322cff6b29cac6489c`. It was written only at
`0x20000`; the write hash, independent `verify_flash`, factory-identical partition table and a
clean content-suppressed 35-second boot observation passed. Bootloader, partition table, NVS,
Wi-Fi credentials and assets were not rewritten.

On 2026-09-04, fresh consent covered exactly one microphone purpose and no automatic retry. From a
ready, authenticated `head=false` baseline, the operator touched once, said
`今日の日付を教えて`, released and made no further contact for at least ten seconds. The final run
accepted 63 input frames, sent 129 output frames, and recorded one STT, one Hermes and one completed
turn plus two TTS segments. The pre-existing Bridge restart baseline remained at two connections
and one disconnection: there were zero connection, disconnection, underrun, overflow, decode, auth
and timeout deltas, and `active_turns` returned to zero. Runtime logs contained exactly one
`turn.started` followed by one `turn.completed`. The operator heard and understood the answer and
reported no `Connecting Bridge` toast, abnormality or additional contact. No recording was
retained; camera and head motion were not used. Metrics measured 12.134 seconds to first audio and
20.881 seconds end to end.

## Live physical CAM-002 vision and sustained-touch follow-up

CAM-002 live physical vision turn is PASS. Fresh privacy consent covered one capture, one live
Hermes vision request and one spoken response, with no automatic retry. The production lifecycle
recorded `capture_total +1`, 100 output frames, DELETE returned 204 and `files_remaining=0`.
The operator heard and understood the answer, confirmed that the description matched the camera
scene, and reported no `Connecting Bridge` toast, unexpected display change, physical contact or
abnormality. The JPEG was never displayed or printed and was deleted immediately.

The same observation window also contained a separate unsolicited failed turn with one no-contact
input frame and no STT request before the accepted vision turn. The earlier three-sample debounce
evidence remains historical, but did not reject this shorter burst. A failing test preceded the
smallest follow-up: six consecutive 50 ms press samples and three consecutive release/idle samples.
Source commit `d88f6df` passed a pre-flash full gate with 438 tests passed at 85.45% coverage and
22/22 Firmware CTest. Its retained motion-locked candidate is
`firmware/build-hermes-touch-filter-d88f6df/stack-chan.bin`, 3,920,848 bytes, SHA-256
`32ec714f11a7c906e6ff73f3c7813f3ed5a0fb06328df1b6db0acba1ae54d881`. The app-only write and
independent digest matched. A clean content-suppressed boot discarded 13,251 serial bytes with no
boot-loop, reset, panic, watchdog, stack, heap, brownout or camera-error marker.

Fresh consent then covered one 60.000-second no-touch window followed by one intentional
approximately one-second touch and no speech. The quiet phase produced no input lifecycle. The
intentional phase produced exactly one lifecycle with 20 Opus frames and 2,878 bytes, followed by a
10.001-second post-touch quiet window; there was no automatic retry and all audio content was
discarded. The operator confirmed the requested single touch/release, no speech, no screen change,
no other physical contact and no abnormality. The strict aggregate reported
`connection_stable=false`; setup timing was not retained, so this auxiliary result is not used as
connection-stability evidence. The bounded sensor counts and operator observation establish the
sustained-touch physical regression; the separate HW-05 run remains the connection-reliability
evidence.

The final documentation full gate completed with 439 tests passed in 32.52 seconds at 85.45%
coverage, 22/22 Firmware CTest, locked-dependency verification and a clean ESP-IDF v5.5.4 build.
Its temporary 3,920,848-byte verification image had SHA-256
`fb4193c340c29fc9e5861b81de85a113da91bedd96969ab3d44a7550873f09ac`; it is build evidence and
was not flashed.

| Scenario | Result | Evidence |
| --- | --- | --- |
| HW-01 Factory backup | **PASS** | Unique device reviewed; pre-flash boot/security/partition evidence captured; 16 MiB backup size, per-region device digests, stored SHA-256 and final whole-device digest all verified |
| HW-02 Boot | **PASS** | Stable custom boot, interactive USB provisioning, bounded NVS writes, Wi-Fi, authenticated hello and operator-confirmed physical display are Green. The initial debounce correction and the later `d88f6df` sustained six-sample press filter are flashed/digest/boot verified; the latest 60.000-second no-touch and single deliberate-touch lifecycle are physically Green |
| HW-03 Status | **PASS** | Authenticated physical hello plus `device.get_status` and `device.get_info` returned successfully; all three identify `M5STACK-K151`, and the device remained connected |
| HW-04 Body | **PASS** | Brightness 35, dim-blue LEDs, corrected happy eyes and comparative volume 45/85 are physically Green. The source-backed conservative K151 profile and authenticated-Bridge-only candidate are host/build/flash Green. Exact `yaw=10` and `pitch=40` commands established positive yaw and decreasing-pitch direction under clean machine observation. A final separately approved `head.home` moved upward once from measured pitch 40.3 to 44.3 degrees, inside the 0/45 home tolerance, with complete clean machine evidence and no abnormality or contact. Historical inconclusive/fail-closed attempts remain recorded |
| HW-05 Reconnect | **PASS** | The final confirmed outage to re-registration was 15,697.6 ms including a deliberate 3.0-second hold; simultaneous serial observation saw no reset/panic/watchdog marker, the same K151 returned with `head=false`, and the operator saw both reconnect toasts. `Connecting Bridge` stacking below another toast remains a UX follow-up |
| HW-06 Audio output | **PASS** | The corrected fixed Japanese candidate was machine-recognized before transmission and heard intelligibly through the physical Opus/resample/internal-speaker path; all 30 frames completed, state returned to IDLE, volume restored 85→70 and error/underflow counters stayed zero |
| HW-07 Audio input | **PASS** | Separately consented short speech reconstructed/validated a private mode-0600 WAV, measured volume/noise/SNR, passed VAD and ended for silence; an intentionally silent held-touch run independently stopped for maximum duration. Both WAVs were immediately deleted and no content left the host |
| HW-08 STT | **PASS** | Production `small`/CPU/INT8 faster-whisper recognized all three ephemeral Japanese patterns (one equivalent kana/punctuation rendering) in 3,689/2,150/2,238 ms; empty speech returned an empty result in 10,961 ms; no audio retained |
| HW-09 Hermes | **PASS** | Loopback-only Hermes v0.20.0 health/readiness and three production Responses/SSE turns passed: greeting 2,721 ms, correct date 5,665 ms, and explicit `ascii-art` Skill 8,590 ms with two `skill_view` calls |
| HW-10 Full voice turn | **PASS** | One freshly consented physical touch and utterance completed exactly one local-STT/live-Hermes/live-TTS/speaker turn. The operator heard and understood the answer; machine evidence showed 63 input frames, 129 output frames, one completed turn, two TTS segments and zero transport/audio/error deltas. No recording was retained |
| HW-11 Cancel | **PASS** | The first audible 880 Hz playback was physically interrupted, queues/state cleared, and a distinct second audible turn entered SPEAKING and completed; final queue/device/input counters were zero and the operator confirmed both sounds without contact |
| HW-12 Camera | **PASS** | On `8ad0489`, one newly consented command completed authenticated JPEG capture/upload, validation, fetch and TTL purge with a stable connection, clean serial markers and no retained media. A later separately consented capture completed live Hermes vision and an accepted spoken answer, making CAM-002 physical vision Green |
| HW-13 Failure handling | **PASS** | Wrong-token, local-public-contract Hermes-stop, HTTP-WAV TTS-stop and camera-failure recovery are Green. One attended device-local 15-second Wi-Fi loss produced exactly one authenticated disconnect, a replacement connection after 11,329 ms and Wi-Fi-connected IDLE recovery; the operator saw `Connecting Bridge` and `Bridge connected` with no abnormality or contact. The diagnostic image was replaced by the verified normal release |

The approved first flash and corrected application reflashes are complete. The previous `7913742`
app matched its retained SHA-256 before the `421457b` correction's retained `bd49497` candidate was
written only at `0x20000`. The new app's write hash and independent read-only digest matched, and a
valid 30-second boot window plus the operator-confirmed happy/idle sequence are Green. Its app
image checksum and internal validation hash are valid, its partition table is byte-identical to
the previous retained build, and its app-only argument file contains only
`0x20000 stack-chan.bin`. The current `d88f6df` app-only update and independent digest supersede
that historical image. At the acceptance checkpoint, bounded helper processes, the Hermes tunnel,
USB attachment and one approved narrow firewall rule remained only through the final
documentation/gate step; the final cleanup section below supersedes that state. A no-touch input activation was reproduced, its debounce correction is
flashed/digest/boot verified, and both the attended no-touch regression and one corrected deliberate
touch are Green. HW-01 through HW-13 are PASS, including the final single-turn HW-10 evidence, and
CAM-002 live physical vision is PASS. Any further camera work and any new microphone-content
purpose require separate explicit privacy consent. The current device contains the `d88f6df`
motion-locked normal release with the attended
Wi-Fi diagnostic disabled. The official-source K151
profile and previously attended authenticated-Bridge-only candidate are host/build/flash Green. Positive yaw, decreasing pitch
and the final machine-valid home are Green, completing HW-04. Any future motion remains a new,
separately approved safety boundary. Do not reinterpret the 15,697.6 ms interval as latency
excluding its intentional 3.0-second outage hold.

Commit `a95319e` added the attended visual-smoke path used in the latest HW-04 run. It requires
`M5STACK-K151`, `head=false` and an explicit brightness restore value; it sends only expression,
LED and brightness commands and attempts every restore even if one restore fails. Physical
brightness and LED observation is Green. The separately isolated expression-only run physically
confirmed the corrected happy eyes and idle restore. Fixed Japanese playback is independently
HW-06 PASS; comparative volume and the bounded yaw/pitch/home sequence are Green, so HW-04 is PASS.

Commit `c94efb5` added label-free `touch_events_total` counting on the Bridge's shared metrics
registry. The later no-touch finding arrived through the Firmware's direct audio-input lifecycle,
not the `touch.*` event family, and no content was retained. The new debounce correction is flashed
and its quiet no-touch regression is Green. The later direct touch-to-audio lifecycle is also Green,
so HW-02 is PASS. Because this Firmware path still does not emit `touch.*`, neither it nor the later
HW-07 capture proves a physical `touch_events_total` increase. The separately consented WAV/quality/
stop-path session above supplies the distinct HW-07 acceptance evidence.

Commit `4d129c7` added the loopback GET-only HW-05 observer used for all bounded intervals. It does
not control Bridge/device, confirm the display or determine reboot on its own. `e73dc30` established
the global toast path but remained blocked by launcher avatar initialization; `7913742` separated
the notification path and is physically flash/digest/visibility verified. Together with the
simultaneous serial observation and operator confirmation, HW-05 is PASS.

## Final Goal cleanup

Final Goal cleanup is complete. After evidence commit `a49adc8`, the final read-only audit recorded
`StackChanHermesBridge8765` rules=0 and all WSL Hyper-V `DefaultInboundAction=Block`. The reviewed
USB device is `Shared`, not `Attached`, with no WSL serial directory. There is no listener on
8765/8766/8642/50031; temporary TTS and SSH tunnel processes are absent, the SSH control socket is
absent, the temporary touch harness and Goal-owned `/tmp` artifacts are absent, and there is no
capture or audio media. The retained motion-locked Firmware candidate and verified private factory
backup were not deleted.
