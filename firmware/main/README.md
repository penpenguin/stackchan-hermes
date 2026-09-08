# Firmware integration point

This directory derives from the pinned official StackChan application and board source.
`main.cpp` installs Launcher, Avatar, ESP-NOW, Dance and Setup, starts local services, and
registers the Bridge worker and USB provisioning console. Legacy cloud apps, account linking,
App Center, OTA and image-recognition uploads have been removed.

The `hal/stackchan_bridge_*` adapters implement protocol v1 using the selected Bridge only.
mDNS candidates must be private or link-local IPv4 unicast addresses; explicit Bridge URLs may
name external servers. Capture uploads use the same host and port and reject redirects.
`hal/board/hal_bridge.cc` owns local audio and scheduled tasks independently of the former AI
application. Power saving and reboot selection use local device settings and installed app names.

`CMakeLists.txt` selects shared Xiaozhi hardware/audio/display sources explicitly, and prepares
a hash-checked local Wi-Fi configuration component without OTA settings. Cloud application,
MQTT/audio protocol, cloud MCP and OTA translation units are excluded from the build.
See [network policy](../../docs/network-policy.md) and [upstream changes](../UPSTREAM.md).
The release head-motion lock and conservative K151 motion limits remain enforced.
