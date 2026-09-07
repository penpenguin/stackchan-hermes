# ADR-0004: Audio pipeline and codec binding

- Status: Accepted and implemented; codec paths are tested
- Date: 2026-08-28

## Decision

Use 16 kHz mono signed-16 PCM as the Bridge logical format and Opus packets on the device link.
Select `opuslib-next` (locked) over the unmaintained original `opuslib`, backed by system libopus.
Keep ffmpeg as a conversion fallback, not the streaming implementation. STT/TTS remain adapters;
local faster-whisper is an optional dependency.

## Consequences

The current host can find `libopus.so.0`; exact 20/40/60 ms packet interoperability is
contract-tested, and physical input/output paths are Green. macOS/Windows packaging remains future
work. A one-maintainer binding is a supply-chain/maintenance risk, so the wrapper interface keeps
replacement local and dependency audits remain required.
