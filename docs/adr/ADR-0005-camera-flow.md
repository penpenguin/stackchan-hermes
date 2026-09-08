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

## 2026-09-08: capture protocol 2

This amendment supersedes image-save-only success and independent command/upload waits.
Both hello directions now require `capture_protocol_version=2`; legacy camera peers are rejected.
The outer v1 envelope and HTTP routes remain unchanged.

One monotonic reservation deadline covers acceptance, camera capture, JPEG encoding, HTTP and
Firmware cleanup. Control success requires a saved image plus a matching SHA-256/size completion
proof sent after the worker joins and camera busy is released. HTTP receipt lookup resolves an
ambiguous upload response before retry; an owned identical duplicate is idempotent only within
the original deadline. Terminal transaction states never reopen.

Completion notification has a bounded queue and explicit Bridge ACK, independent of camera
ownership. Capture HTTP executes in its worker with nonblocking DNS/TCP/TLS and finite I/O
budgets; frame dequeue uses a reviewed finite-wait ioctl extension. Managed source caches stay
unchanged and derivative hashes/actual compilation inputs are verified. See the
[wire contract](../protocol-v1.md#capture-transaction-protocol-2) for states, quotas and retry rules.

Fault-injection and build evidence do not identify the original device's root cause or establish
physical timing. Stationary hardware verification remains a separate authorized step.
