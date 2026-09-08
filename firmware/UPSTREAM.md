# Firmware upstream pin

Status: **vendor snapshot imported; unchanged baseline and integrated overlay builds verified**

- Repository: `https://github.com/m5stack/StackChan.git`
- Default branch observed: `main`
- Pinned commit: `1b5765599fba8aaad1811d9a79358ccc7051f5f3`
- Pinned `firmware/` tree: `a981688092155fb4a84c530575e70c7f83ab42e6`
- Upstream Firmware version: `1.5.1`
- Import method: reviewed vendor snapshot
- Required toolchain: ESP-IDF `v5.5.4`, commit
  `735507283d5b2f9fb363a1901172dbd9e847945d`
- Baseline license: MIT (`firmware/LICENSE` at the pinned commit)
- Board default: M5Stack StackChan/CoreS3, expected product code `M5STACK-K151`

## Review and build evidence

The exact source was checked out in an isolated review directory before import. The official
`fetch_repos.py` resolved six Git dependencies; their tags, commits, licenses and the reviewed
xiaozhi patch digest are frozen in `upstream-lock.json`. The ESP-IDF Component Manager used 59
downloaded components plus the IDF entry already recorded by upstream `dependencies.lock`;
`verify_managed_components.py` recomputes all 59 local content hashes. Available upgrades were not
applied.

The unchanged baseline produced this evidence on 2026-08-28:

- official host test: 1/1 passed;
- `idf.py build`: exit 0 with target `esp32s3`;
- `stack-chan.bin`: 3,786,944 bytes;
- `stack-chan.bin` SHA-256:
  `32abe637f2fb7f600c0a64cf2c8e06aad569bc0989a74140620c2e792d5174b2`;
- smallest app partition: `0x4f0000`, with 27% free;
- flash size: 16 MiB; partition-table offset: `0x8000`;
- build configuration: Secure Boot and Flash Encryption disabled.

Before custom integration, the imported workspace independently passed `verify-firmware.sh` on
2026-08-29 after verifying
all six Git repositories and 59 managed components. Its 3,786,944-byte app SHA-256 was
`177b1c7e8c2a8f9fc6c4b55445808e70d96cd85f31f3e209f3d37cb51b310e9f`; partition table and
generated-assets hashes matched the isolated review build. The app binaries differ in only 72
bytes because official defaults enable app/bootloader compile timestamps. Binary hashes therefore
identify individual builds; source/toolchain provenance, size and partition evidence are the
reproducibility contract for this unchanged baseline.

The baseline emitted non-fatal upstream warnings for `_IO` macro redefinitions, unused variables
and one trailing-whitespace line in the reviewed xiaozhi patch. These warnings were not hidden or
fixed before the baseline build.

## Integrated local overlay

The vendor snapshot remains pinned. Bridge protocol behavior is isolated in
`components/stackchan_bridge_client/`, with the local app/HAL changes described below. The reviewed
xiaozhi patch now also exposes bounded decode-result and playback-gain hooks needed by the
project-owned audio service; its exact diff SHA is locked. The integrated lock contains 60 managed
components plus IDF after adding official `espressif/mdns==1.11.3`.

On 2026-08-29 the initial Bridge-enabled/USB-provisioning configuration passed 17/17 host C++
tests and an ESP-IDF `esp32s3` build. Its app image is 3,921,680 bytes (24% app-partition
headroom), SHA-256
`5039bbb1a45c2e5ea70cab292f40101f3073f5baff6d4dadd48aba071847de9f`. This is build evidence,
not a physical or reproducible-bitstream claim; official compile timestamps make each build hash
specific.

Physical use subsequently exposed five integration defects, each corrected Red→Green: invalid
zero-length REPL history (`fca58cf`), an output-only secondary USB console (`ab7f1e4`), an
ESP-IDF NVS key longer than 15 bytes (`a6c882e`), JSON `null` for absent command-envelope fields
(`4abe3d9`), and a transport name used as hardware identity (`0a3bad2`). The physical key for the
logical discovery setting is now `bridge.discovery`, absent envelope fields are omitted, and the
wire identity is `M5STACK-K151`. These are project overlay/Bridge changes; the vendor snapshot and
dependency pins remain unchanged.

On 2026-08-31 the current configuration passed 18/18 Firmware CTest targets and the complete host
gate. The retained primary-USB/motion-locked app is 3,918,256 bytes, SHA-256
`a2bb5f5b124eaea6eae27961d4f87fad0257039b0a1d920bf6ebb6d18432faae`, with 24% headroom. The
final combined gate independently rebuilt a 3,918,256-byte image from a fresh temporary sdkconfig,
SHA-256 `d8b829ff91bf09ef2357bfb0ac4c4e5f575e25f5d106df5b3936413370cb5d3b`, also with 24%
headroom. Generated configuration checks require the Bridge client, primary USB Serial/JTAG
console, USB provisioning and physical head-motion lock.

## Distribution fonts and notices

On 2026-09-07, project build selection stopped compiling the locked font component's Puhui,
merged Noto and Font Awesome glyph data because their exact input licenses could not be verified.
The MIT runtime helpers and attributed CC-BY-4.0 Twemoji remain. `release-fonts/` contains
replacements generated from pinned Noto and Material Icons inputs; the UI Montserrat font was
also regenerated from a pinned OFL input. Dependency commits and content hashes remain unchanged.

`tools/verify_release.py` checks compiled font sources, asset/model bytes, SDK and dependency
identity, selected archives and the five distributable CoreS3 images. It can bundle these images
with their notices. Font provenance, applicable terms and the build evidence are documented in
[`release-fonts/README.md`](release-fonts/README.md) and the
[distribution review](../docs/license-audit.md). This build has not been tested on hardware.

## Local CFW and cloud removal

On 2026-09-08, the project removed legacy AI.Agent, EzData, account linking, App Center,
cloud Avatar/calls, image-recognition uploads and OTA from the imported main sources.
Updates use USB. Local display, BLE, ESP-NOW, dance, Wi-Fi setup, audio, camera and Bridge
protocol v1 remain. Local audio ownership, scheduled sounds, power saving and app-name reboot
selection no longer depend on the Xiaozhi application. Legacy cloud settings are not read.

The source list now explicitly selects shared hardware/audio/display code. Xiaozhi Application,
MQTT/audio protocols, cloud MCP, OTA, diagnostic audio upload and runtime asset downloading are
excluded. The revised [MIT patch](patches/xiaozhi-esp32.patch) also removes their dependencies
from shared sources; its exact diff digest is checked by [upstream-lock.json](upstream-lock.json).
The fixed Git commits are unchanged. The patch is stored as a verbatim upstream diff, including
original whitespace on context/deleted lines; added source lines pass the whitespace check.
The Wi-Fi board patch also closes provisioning on setup completion/cancellation, resumes saved
station connections and suppresses AP fallback until setup is explicitly reopened. A host C++
test compiles the exact patched board sources with deterministic Wi-Fi/timer fakes to cover
offline exit, saved/pending/connected stations, delayed timeouts and repeated setup entry.

The pinned `78/esp-wifi-connect@3.1.2` MIT configuration page and API formerly retained `ota_url`.
[The local patch](patches/esp-wifi-connect.patch) removes that field, its NVS reads/writes and
page controls. [Its manifest](patches/esp-wifi-connect.json) records source/output hashes and the
existing license evidence (the MIT text was supplemented from a later upstream commit).
`tools/prepare_local_wifi.py` validates and stages only these files in the build directory;
the managed cache and its lock hash stay unchanged.

The Apache-2.0 `78/esp-ml307@3.6.5` network factory is replaced by
[a marked derivative](components/stackchan_bridge_client/esp_network.cpp) returning no MQTT/UDP
transport. Only its HTTP/TCP/TLS and reviewed WebSocket sources are compiled; MQTT and cellular
modem sources are excluded, and no MQTT sender is linked. The managed license record identifies
the original file and derivative by SHA-256. DNS, DHCP and SNTP use the SDK networking stack.

The release gate checks compile commands, demangled ELF symbols, legacy configuration strings
and the staged Wi-Fi source/page hashes. Host C++ tests cover discovery, offline/failed Bridge
sessions, local power/reboot/tasks and the actual locked HTTP transport's redirect behavior.
Python tests cover all Hermes/STT/TTS HTTP calls with an injected redirect-enabled client.
[Network policy](../docs/network-policy.md) records destinations and local setup.
[The release record](../docs/license-inventory/cores3-release.json) identifies the verified
binaries, assets and linked archives; compiler timestamps still make hashes build-specific.
No flash, physical local-feature test or device packet capture was performed for this change.

## K151 motion safety profile

K151 conservative motion profile: yaw `-45..45` degrees, pitch `5..85` degrees, speed `1..30`
(default `15`), home `0/45` degrees.

This is a deliberately narrower project profile derived from two official sources:

- pinned official commit `1b5765599fba8aaad1811d9a79358ccc7051f5f3` defines horizontal
  `-128..128` degrees, vertical `3..87` degrees at the HAL, and describes `+/-45` degrees plus
  underlying speed `150` as natural interaction values;
- [M5Stack's official StackChan servo documentation](https://docs.m5stack.com/ja/arduino/stackchan/servo)
  documents the full horizontal/vertical and `0..1000` speed domains, while explicitly recommending
  vertical `5..85` degrees because endpoint stall can damage the servo.

The Bridge protocol speed is multiplied by ten at the official HAL adapter, so the project maximum
`30` becomes underlying speed `300`, matching the official vertical example and remaining far below
the official maximum. Project `head.home` uses the midpoint `0/45` instead of an endpoint. Bridge,
MCP and Firmware reject values outside the profile rather than clamping; the official HAL angle
limits provide a final clamp for local autonomous paths, and continuous yaw PWM is disabled in the
Hermes build. The release configuration still defaults to
`CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y`. No unlock, flash or physical head command is implied
by this host-side profile.

Do not move the source or dependency pins silently. Before any flash, follow
`../docs/hardware-setup.md`; a verified 16 MiB factory backup and unique serial port are mandatory.
