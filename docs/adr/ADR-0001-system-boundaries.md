# ADR-0001: System boundaries

- Status: Accepted
- Date: 2026-08-28

## Decision

Use thin StackChan firmware, a standalone Python Bridge, and an independently operated
HermesAgent. Hermes interaction is limited to public HTTP/SSE APIs and stdio MCP. The local
Control API is loopback-only; only authenticated device traffic reaches the LAN listener.

## Consequences

The ESP32 remains responsive and physically safe without an LLM. The Bridge can be tested with a
Simulator and upgraded without forking Hermes. More explicit protocol/state/adapters are required,
but failures and credentials stay within clearer boundaries.
