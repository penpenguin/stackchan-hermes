# Firmware tests

The Firmware host suite contains the imported motion helper test plus project-owned protocol,
state, reconnect, settings/discovery/provisioning, command, audio/playback completion, camera, event,
bounded WebSocket frame/transport and session tests:

```bash
cmake -S firmware/tests -B firmware/build-host-tests
cmake --build firmware/build-host-tests
ctest --test-dir firmware/build-host-tests --output-on-failure
```

The shared-console tests compile the production C/C++ console, BLE input and Hermes provisioning
sources with SDK/RTOS/NVS fakes. They cover one-time startup, command registration before input
starts, pairing input and timeouts, queue/registration/startup failures, and the USB Serial/JTAG,
USB CDC and UART configurations with provisioning or the whole Bridge disabled. These tests do
not exercise the real NimBLE stack or LVGL app transitions.

Platform and physical acceptance continues with:

- ESP-IDF Unity/pytest-embedded tests for platform integration;
- explicitly recorded hardware smoke tests for physical I/O.

Hardware tests never substitute for a failing automated test where behavior can be isolated on the
host. Physical motion remains blocked while the contract limits are unset.
