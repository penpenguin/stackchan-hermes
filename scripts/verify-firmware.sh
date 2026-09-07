#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if ! command -v idf.py >/dev/null 2>&1; then
  echo "ERROR: ESP-IDF v5.5.4 is not active; idf.py was not found." >&2
  echo "See docs/hardware-setup.md. This check is intentionally not skipped." >&2
  exit 2
fi

if [[ ! -f firmware/CMakeLists.txt ]]; then
  echo "ERROR: the pinned official firmware baseline has not been imported yet." >&2
  echo "See firmware/UPSTREAM.md before importing or modifying firmware." >&2
  exit 2
fi

cd firmware
python3 ./verify_upstream_dependencies.py
python3 ./verify_managed_components.py
cmake -S tests -B build-host-tests
cmake --build build-host-tests --parallel 2
ctest --test-dir build-host-tests --output-on-failure

# Build from a fresh, temporary sdkconfig so an ignored local configuration cannot silently
# disable the Hermes integration under verification.
firmware_verify_dir="$(mktemp -d /tmp/stackchan-hermes-fw-verify.XXXXXX)"
cleanup_firmware_verify_dir() {
  case "$firmware_verify_dir" in
    /tmp/stackchan-hermes-fw-verify.*) rm -rf -- "$firmware_verify_dir" ;;
  esac
}
trap cleanup_firmware_verify_dir EXIT

firmware_defaults="$PWD/sdkconfig.defaults;$PWD/sdkconfig.hermes.defaults"
idf.py -B "$firmware_verify_dir/build" \
  -D SDKCONFIG="$firmware_verify_dir/sdkconfig" \
  -D SDKCONFIG_DEFAULTS="$firmware_defaults" \
  build

python3 tools/verify_release.py "$firmware_verify_dir/build"

required_motion_lock="CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y"
if ! grep -Fxq "$required_motion_lock" "$firmware_verify_dir/sdkconfig"; then
  echo "ERROR: Firmware verification build does not enforce the Hermes head-motion lock." >&2
  exit 2
fi

required_usb_console="CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y"
if ! grep -Fxq "$required_usb_console" "$firmware_verify_dir/sdkconfig"; then
  echo "ERROR: Firmware verification build does not provide an interactive USB provisioning console." >&2
  exit 2
fi

firmware_image="$firmware_verify_dir/build/stack-chan.bin"
firmware_size_bytes="$(wc -c < "$firmware_image")"
firmware_sha256="$(sha256sum "$firmware_image" | awk '{print $1}')"
printf 'Firmware verification image: %s bytes\n' "$firmware_size_bytes"
printf 'Firmware verification SHA-256: %s\n' "$firmware_sha256"
