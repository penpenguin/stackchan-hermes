# ADR-0003: Hermes public Responses API

- Status: Accepted
- Date: 2026-08-28

## Decision

Use public health/capabilities/models/skills/toolsets endpoints and streaming
`POST /v1/responses`, with per-device conversation names and `X-Hermes-Session-Key`. Inline image
input is permitted only at the Bridge → Hermes boundary. Do not use Dashboard `/api/ws`, internal
imports, databases, or patches.

## Consequences

Capability detection is a readiness gate. Responses SSE/function progress need a defensive parser
and Mock Hermes coverage. Conversation transcript scope and stable long-term memory scope remain
separate. No local runtime was available to verify capabilities during Phase 0.
