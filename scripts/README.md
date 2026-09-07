# Scripts

Implemented entrypoints:

- `bootstrap-check.sh`: read-only offline host diagnosis.
- `validate-protocol.py`: schema/example contract validation.
- `check-secrets.py`: failure-producing `detect-secrets` baseline check over tracked and
  non-ignored untracked files.
- `verify-host.sh`: lock, format, lint, type, tests/coverage, protocol, secrets, audit, doctor.
- `verify-firmware.sh`: six Git/60 managed dependency checks, 24 host C++ tests, then a fresh
  temporary Bridge-enabled ESP-IDF build using `sdkconfig.hermes.defaults`.
- `verify.sh`: final host + Firmware gate.
- `generate-device-token.py`: compatibility wrapper for the one-time token CLI.
- `run-simulator-e2e.sh`: real Gateway/Simulator capture and voice flows plus reconnect tests.
- `backup-firmware.sh`: dry-run by default; explicit read-only 16 MiB/partition backup with SHA.
- `hardware-reconnect-observer.py`: loopback GET-only observation of a confirmed Control/device
  outage and the target ID/K151/head-lock state returning; it does not stop or start either
  endpoint or prove physical identity by itself.
- `hardware-smoke-test.py`: read-only status by default; a motion-free, automatically restored
  visual-observation path; and a separately guarded small motion path. The motion path sends
  nothing unless the connected device is `M5STACK-K151`, advertises `head=true`, has a verified
  factory backup and receives explicit `--allow-motion` plus a target inside its initial narrow
  range.
- `create-debug-report.sh`: bounded mode-0600 report with optional redacted text logs.

No script installs OS packages, changes shell profiles/Hermes config, flashes by default, or stores
secrets/media in tracked paths.

For an attended K151 visual check while the motion-locked Firmware is connected, pass the known
pre-test brightness explicitly so the script can restore it. The script holds a happy expression,
dim blue LEDs and 35% brightness for the requested interval, then independently attempts all three
restoration commands. It requires `head=false` and never sends a `head.*` command in this mode:

```bash
uv run python scripts/hardware-smoke-test.py \
  --device-id stackchan-001 \
  --safe-visual \
  --restore-brightness 70 \
  --hold-seconds 10
```
