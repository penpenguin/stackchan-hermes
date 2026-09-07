# Observability boundary

Structured redacted logs, machine-readable metrics, correlation IDs, and timing belong here.

`touch_events_total` counts accepted `touch.*` events without device, coordinate or content
labels. Compare its value immediately before and after an attended physical touch; an unchanged
value is not touch evidence. Use `audio_input_frames_total` and `active_turns` separately to
distinguish sensor delivery from microphone/turn behavior.
