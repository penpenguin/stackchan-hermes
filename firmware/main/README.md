# Firmware integration point

This directory contains the pinned official StackChan application and board source. Keep direct
changes here to the smallest reviewed registration/integration points needed to run the custom
Bridge client from `../components/stackchan_bridge_client/`.

`main.cpp` registers the Bridge worker and optional USB provisioning console. The
`hal/stackchan_bridge_*` adapters use official network/WebSocket, audio, display, touch and camera
interfaces for protocol v1, mDNS/fallback discovery, state presentation, bounded audio and JPEG
upload. Remote head capability remains false and motion commands remain reject-all until official
configuration and K151 physical evidence agree.
