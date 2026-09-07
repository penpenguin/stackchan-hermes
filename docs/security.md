# Security and privacy baseline

## Trust boundary

- Device gateway and capture upload are limited to a trusted LAN and require device bearer auth.
- Control API, metrics with sensitive labels, and Hermes API stay on loopback.
- v1 may use unencrypted `ws://` only on that LAN; the eavesdropping risk remains explicit.
- LAN-external exposure, wildcard CORS, disabled TLS verification, and public relay are forbidden.

## Secrets

Hermes API keys exist only on the Bridge host. Firmware stores only its own device token in NVS.
They must never share a value. Tokens are prohibited in URLs, payloads, logs, reports, fixtures,
and tracked config. `.env`, local TOML, keys, captures, recordings, reports, and flash backups are
ignored by default.

## Media

Audio is not persisted by default. `audio.debug_save_enabled=true` is an explicit privacy opt-in;
the runtime warns, writes only generated UUID WAV files with mode 0600, and purges them after the
configured TTL. Captures use unguessable IDs, ownership checks, JPEG marker/dimension/size checks,
generated non-overwriting mode-0600 paths, and a default ten-minute TTL. Persistent captures are
also explicit opt-in. Raw media or Base64 data never appears in logs or debug reports.

## Resource limits

Runtime config bounds JSON/frame/audio/image size, connections, authentication/request/capture
rates, concurrent scrypt verification, recording, commands, captures, segmentation and external
timeouts. Protocol models, schemas and Firmware guards enforce the shared wire limits. Firmware
uses bounded audio queues, a 256-ID duplicate cache, finite camera retries and a
three-invalid-message/ten-second close window.

## Runtime enforcement evidence

- scrypt-derived token records and constant-time comparison; raw bearer values are never stored
  in registry/config repr or URL query parameters;
- authentication precedes hello/media/command processing and capture body reading; WebSocket and
  capture authentication share a global token bucket and a cancellation-safe concurrent-scrypt
  limit before work enters the thread pool;
- Control/Hermes URL validation rejects non-loopback management surfaces and embedded credentials;
- no CORS middleware/wildcard policy is installed;
- structured logs use an allow-list and privacy-debug is required for transcript logging;
- `scripts/create-debug-report.sh` reads no config/environment values and redacts supplied logs;
- `scripts/check-secrets.py` and dependency audit run in every host gate.

## Dependency and supply-chain policy

- Python dependencies are locked with hashes in `uv.lock` and audited before release.
- GitHub Actions are pinned to full commit SHAs.
- Firmware baseline/dependencies remain pinned and their licenses/notices are preserved.
- The project-added Firmware discovery dependency is official `espressif/mdns==1.11.3`
  (Apache-2.0), content-locked with the other managed components.
- No third-party code is copied from a repository with unclear applicable licensing.
