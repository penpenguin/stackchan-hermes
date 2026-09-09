# MCP server boundary

The stdio server maps twelve safe MCP tools to the loopback Control API. It logs only to stderr
and returns typed disconnected-device errors rather than crashing.

`stackchan_speak(device_id, text)` accepts up to 1,000 plain-text characters and immediately
returns a `turn_id`. `stackchan_get_speech_status(device_id, turn_id)` reports the background
result, and the existing `stackchan_cancel_speech` stops it. Any active conversation causes
`TURN_BUSY`. See [operations](../../../../docs/operations.md#direct-speech-from-mcp) for lifecycle,
history limits and error semantics.
