# ADR-0006: Import the reviewed official Firmware as a vendor snapshot

- **Status:** Accepted and implemented for the baseline
- **Date:** 2026-08-28

## Decision

Import the `firmware/` tree from official `m5stack/StackChan` commit
`1b5765599fba8aaad1811d9a79358ccc7051f5f3` as a vendor snapshot. Preserve its MIT notice, upstream
dependency lock and patch. Record the source tree, ESP-IDF commit, resolved Git dependency commits,
licenses and critical file hashes in `firmware/upstream-lock.json`; verify fetched dependencies
and all locked managed-component content before every Firmware build.

Custom behavior is isolated in `stackchan_bridge_client` and the smallest necessary app/board
registration points. Community forks and files with ambiguous applicable licenses are behavioral
references only.

## Evidence and rationale

The exact pin was fetched into an isolated review directory and built unchanged with ESP-IDF
v5.5.4. Its official host test passed 1/1 and `idf.py build` exited 0. The tracked Firmware snapshot
contains 232 files and approximately 3.2 MB, so vendoring keeps review and offline source inspection
practical without committing fetched Git repositories, 59 downloaded managed components or build
output.

A Git subtree was rejected because the destination `firmware/` already contains the project
contract and integration boundary, making subtree ownership and future merges unnecessarily
ambiguous. A build-time source fetch was rejected because it would make the primary source tree and
review dependent on network availability. A submodule, community-fork baseline, guessed servo
limits and flashing an unbuilt image remain rejected.

## Consequences

Upstream updates require an explicit pin change, license/dependency diff, regenerated provenance
lock, host tests and an unchanged candidate baseline build before custom code is replayed. The
snapshot does not authorize flash: unique K151 identity, factory backup and physical safety gates
remain separate evidence.
