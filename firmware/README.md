# Firmware workspace

The official M5Stack StackChan Firmware v1.5.1 source is imported as a reviewed vendor snapshot
from the exact commit recorded in `UPSTREAM.md` and `upstream-lock.json`. The upstream MIT notice is
preserved in `LICENSE`. Fetched Git dependencies and ESP-IDF managed components remain ignored build
inputs; the two verification scripts reject commit, reviewed-patch, lock-hash or content drift
before a build.

## Verify the integrated Firmware

Activate ESP-IDF v5.5.4 only in the Firmware shell, then run:

```bash
python3 ./fetch_repos.py
python3 ./verify_upstream_dependencies.py
idf.py reconfigure
python3 ./verify_managed_components.py
cmake -S tests -B build-host-tests
cmake --build build-host-tests
ctest --test-dir build-host-tests --output-on-failure
cd ..
./scripts/verify-firmware.sh
```

The final script verifies six fetched Git repositories, 60 downloaded ESP Component Registry
resolutions and 26 host C++ tests. The WebSocket wire test compiles the modified transport against
the locked `78/esp-ml307` headers, so managed components must be resolved first. The final script
then creates a fresh temporary `sdkconfig`, applies
`sdkconfig.hermes.defaults`, and builds the Bridge-enabled image so an ignored local `sdkconfig`
cannot silently disable the integration. The original reviewed baseline had 59 managed
components; official `espressif/mdns==1.11.3` is the one integrated addition.

The retained no-touch correction checkpoint predates the playback-completion target and recorded
19 host C++ tests; that historical evidence remains distinct from the current 26-test suite.

`verify_managed_components.py` recomputes every downloaded component hash locally, without
trusting only `.component_hash`. Do not run `idf.py update-dependencies` as part of reproduction.
A deliberate dependency update requires a new lock, license review, host tests and build evidence.

## Custom integration and safety

Read `UPSTREAM.md`, `stackchan-bridge-client.contract.json`, and `../docs/hardware-setup.md` before
modifying or flashing Firmware. Custom transport/state behavior is isolated in
`components/stackchan_bridge_client/`; thin adapters in `main/hal/stackchan_bridge_*` connect it
to the official network, display, touch, audio and camera abstractions. Runtime settings are
validated and stored in NVS through the `stackchan-hermes` USB serial command. The device token is
never compiled into the image.

The contract now records a source-backed conservative K151 profile: yaw `-45..45` degrees, pitch
`5..85` degrees, speed `1..30` (default `15`) and home `0/45` degrees. Bridge, MCP, the Firmware
executor and the official HAL adapter enforce that profile, while the normal release configuration
still has `CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y` and advertises `head=false`. A successful
build is not permission to flash or move hardware. A uniquely identified K151, verified 16 MiB
factory backup, reviewed security/partition state, a separately verified unlocked candidate and
explicit flash and physical-motion approvals remain mandatory.

### Attended Wi-Fi loss diagnostic

The normal release defaults keep `CONFIG_STACKCHAN_HERMES_ATTENDED_WIFI_CYCLE=n`. For the physical
HW-13 Wi-Fi-loss observation only, an explicitly reviewed diagnostic image may set it to `y` while
retaining USB provisioning, a USB Serial/JTAG or USB CDC console, and the physical head-motion
lock. The resulting local USB command is:

```text
stackchan-hermes cycle-wifi 15
```

The duration must be 5 to 30 seconds. The command is accepted only when station mode is currently
connected and only once per boot. It stops and restarts the device's own Wi-Fi station and does not
modify stored Wi-Fi credentials. This is an actual device-local Wi-Fi outage; it does not simulate
a failed access point or router.

Do not enable or flash this diagnostic until the unique K151, verified factory backup, partition
and security state, exact app image digest, and recovery image have all been reviewed. Require one
explicit approval for an app-only diagnostic flash and a fresh approval before sending the single
cycle command. Observe the user-facing disconnect state and automatic Bridge recovery while a
content-suppressed serial monitor checks for reboot, panic and watchdog markers. After recording
the bounded result, use a separately reviewed app-only flash to restore a normal release image
with this option disabled; that restoration also requires explicit approval.
