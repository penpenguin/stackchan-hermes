# State machines

Status: **implemented and host-tested for Protocol v1** (2026-08-29).
Physical connection, input, output, cancellation, camera, motion and failure-recovery transitions
are Green. Live local STT HW-08, live text/Skill Hermes HW-09 and the physical full-voice HW-10
are PASS. CAM-002 live physical vision turn is PASS.

The connection and audio-stream machines are normative in `docs/protocol-v1.md`. This document
defines Firmware presentation/safety and Bridge turn ownership. An unlisted transition is
forbidden, leaves safety-critical state unchanged, and returns/records `INVALID_STATE`.

## Firmware state machine

States are `BOOTING`, `CONNECTING_WIFI`, `CONNECTING_BRIDGE`, `IDLE`, `LISTENING`, `SPEAKING`,
`ERROR`, and `UPDATING`. Thinking is a presentation overlay while the physical state is `IDLE`;
it does not own a separate media stream.

| Current | Event | Next | Effects |
| --- | --- | --- | --- |
| `BOOTING` | initialization succeeds | `CONNECTING_WIFI` | load validated settings; keep servos passive/safe |
| `BOOTING` | hardware/config failure | `ERROR` | stop media/motion and show bounded diagnostic |
| `CONNECTING_WIFI` | Wi-Fi connected | `CONNECTING_BRIDGE` | reset stale sockets; begin discovery/fixed URL connect |
| `CONNECTING_WIFI` | retryable failure | `CONNECTING_WIFI` | bounded backoff; UI remains responsive |
| `CONNECTING_WIFI` | fatal config/hardware failure | `ERROR` | reject body/media commands |
| `CONNECTING_BRIDGE` | authenticated hello/ack completes | `IDLE` | reset reconnect backoff after healthy interval; resync settings/status |
| `CONNECTING_BRIDGE` | retryable failure | `CONNECTING_BRIDGE` | destroy socket/tasks; bounded backoff with status display |
| `CONNECTING_BRIDGE` | Wi-Fi lost | `CONNECTING_WIFI` | destroy socket/tasks and all stream contexts |
| `IDLE` | local input trigger accepted | `LISTENING` | create mic/encoder queue; listening face; face forward |
| `IDLE` | `audio.output.start` | `SPEAKING` | clear/init playback; preroll; speaking animation |
| `IDLE` | Bridge thinking on/off | `IDLE` | toggle thinking overlay only |
| `IDLE` | authenticated update begins | `UPDATING` | disable motion/media; persist recovery marker |
| `LISTENING` | input end/max/cancel | `IDLE` | close mic stream; clear listening overlay; optionally show thinking |
| `LISTENING` | playback start | `SPEAKING` | end input with explicit reason, then initialize playback |
| `SPEAKING` | playback completed/error/cancel | `IDLE` | flush queue; reset mouth/expression and small motion |
| `SPEAKING` | barge-in trigger | `LISTENING` | cancel playback and flush before opening microphone |
| `IDLE`/`LISTENING`/`SPEAKING` | Bridge socket lost | `CONNECTING_BRIDGE` | destroy streams/tasks; safe pose/presentation; no stale writes |
| any non-updating state | nonrecoverable hardware safety error | `ERROR` | stop media and hazardous movement immediately |
| `ERROR` | explicit recovery succeeds | `CONNECTING_WIFI` | reinitialize bounded resources; no abrupt servo home |
| `UPDATING` | verified update completes | `BOOTING` | reboot through normal initialization |
| `UPDATING` | update fails safely | `ERROR` | preserve recoverable image/settings and show failure |

Entry/exit invariants:

- entering `SPEAKING` always creates an empty playback context before accepting binary packets;
- leaving `SPEAKING` always discards playback and restores mouth/expression;
- leaving `LISTENING` always closes mic/encoder queues and emits at most one input end;
- entering `ERROR` or `UPDATING` rejects body/media commands and disables autonomous motion;
- every disconnect returns the head according to the board-safe policy without abrupt movement;
- reconnection uses a generation/connection ID so an old receive task cannot change new state;
- runtime settings, volume, brightness, head angles, and status are resynchronized after reconnect.

## Bridge turn coordinator

There is at most one active turn per device. States are `IDLE`, `CAPTURING`, `TRANSCRIBING`,
`WAITING_HERMES`, `SYNTHESIZING`, `PLAYING`, `CANCELLING`, `FAILED`, and `COMPLETED`.
`FAILED`/`COMPLETED` are observable terminal states whose cleanup deterministically returns to
`IDLE`.

| Current | Event | Next | Effects |
| --- | --- | --- | --- |
| `IDLE` | accepted touch/button/control/simulator trigger | `CAPTURING` | allocate turn/input stream and start timing |
| `CAPTURING` | second local trigger | `TRANSCRIBING` | request/accept a single normal input end |
| `CAPTURING` | speech end or 15 s maximum | `TRANSCRIBING` | close input, freeze PCM, start cancellable STT |
| `CAPTURING` | cancel/disconnect | `CANCELLING` | stop input and discard queued audio |
| `TRANSCRIBING` | non-empty STT result | `WAITING_HERMES` | store bounded transcript privately; start one SSE request |
| `TRANSCRIBING` | empty/error/timeout | `FAILED` | no Hermes request; record typed failure and user-safe feedback |
| `TRANSCRIBING` | trigger/cancel/disconnect | `CANCELLING` | cancel STT and reject its later result |
| `WAITING_HERMES` | first speakable segment | `SYNTHESIZING` | start cancellable TTS for segment 1 |
| `WAITING_HERMES` | completion with no speakable text/error/timeout | `FAILED` | stop SSE; record mapped error |
| `WAITING_HERMES` | trigger/cancel/disconnect | `CANCELLING` | stop SSE and reject all later deltas |
| `SYNTHESIZING` | first ordered segment ready | `PLAYING` | open output stream and send segment 1 only |
| `SYNTHESIZING` | TTS error/timeout before playback | `FAILED` | discard every segment; send no stale audio |
| `SYNTHESIZING` | trigger/cancel/disconnect | `CANCELLING` | cancel TTS and discard generated segments |
| `PLAYING` | later segment ready | `PLAYING` | enqueue by segment index; never overtake |
| `PLAYING` | all segments/device playback complete | `COMPLETED` | close output once and finalize timing |
| `PLAYING` | TTS/device error | `FAILED` | default policy cancels remaining playback |
| `PLAYING` | new trigger/cancel/disconnect | `CANCELLING` | send `speech.cancel`, flush output, remember optional new trigger |
| `CANCELLING` | all owned tasks/queues acknowledged or timed out | `IDLE` | invalidate cancellation token; optionally start remembered trigger |
| `FAILED` | feedback/cleanup completes | `IDLE` | clear active turn while retaining bounded metrics/error only |
| `COMPLETED` | cleanup completes | `IDLE` | clear active turn while retaining bounded metrics only |

Global rules:

- a raw touch event during `CAPTURING` records telemetry only; Firmware owns the normal input
  end triggered locally, and Bridge must not remove the turn before that end or its deadline;
- every asynchronous completion carries `turn_id` and cancellation generation;
- a stale/mismatched result is discarded and cannot transition state or enqueue playback;
- no device conversation has two concurrent Hermes requests;
- cancel stops STT, SSE, TTS, device playback, and all queues before `IDLE`;
- a trigger in `PLAYING` performs cancel-before-new-turn (barge-in), never overlapping streams;
- disconnect uses the same cleanup ownership as cancellation and leaves no pending command future.

Parameterized unit tests must cover every listed transition plus representative forbidden,
duplicate, timeout, stale-result, cancellation-race, and reconnect cases before runtime use.
