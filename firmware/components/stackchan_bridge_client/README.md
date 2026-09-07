# stackchan_bridge_client

Project-owned ESP-IDF component for WebSocket/device authentication, hello/ack, bounded protocol
state, settings precedence, mDNS result validation, reconnect, command dispatch, audio streams,
capture upload and event generation. Hardware operations go through thin official HAL/BSP
adapters and remain subject to firmware-side safety checks.

The normative implemented contract is `../../stackchan-bridge-client.contract.json`.
Motion limits remain `null`, which means every motion command must be rejected, until the pinned
official board configuration and K151 evidence establish yaw/pitch/speed limits. Do not translate
the Bridge's broader wire range directly into servo movement. Hermes candidate builds also keep
`CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y`; the official HAL servo sink then blocks position,
velocity and torque-enable writes from both Bridge and local app/idle paths while still permitting
torque disable.
