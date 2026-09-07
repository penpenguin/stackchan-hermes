# ADR-0002: Device protocol

- Status: Accepted and implemented for Protocol v1
- Date: 2026-08-28

## Decision

Use WebSocket text frames for bounded versioned JSON control and raw binary frames for Opus.
Start/end control messages assign binary frames to at most one input and output stream per device.
Use authenticated HTTP multipart upload for JPEG captures.

## Consequences

Media avoids Base64 overhead and ordering follows WebSocket semantics. Both sides require strict
state, size, timeout, and duplicate handling. Schema examples are the first contract; Pydantic and
Firmware parsers are triangulated against them.
