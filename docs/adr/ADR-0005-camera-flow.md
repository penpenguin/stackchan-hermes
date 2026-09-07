# ADR-0005: Camera capture flow

- Status: Accepted
- Date: 2026-08-28

## Decision

Use explicit capture requests. Firmware captures a bounded JPEG and uploads it via authenticated
multipart HTTP using a Bridge-issued unguessable ID. Bridge validates ownership, magic, MIME,
size, path, hash, and TTL. It creates a data URL only for the one Hermes Responses request that
needs `input_image`.

## Consequences

No continuous camera stream or persistent media is required. Capture lifecycle and cleanup can be
tested without hardware. MCP ImageContent remains optional; the explicit Responses vision turn is
the required fallback.
