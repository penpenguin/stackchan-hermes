# launchd example

Copy and edit `com.stackchan-hermes.bridge.plist` plus `stackchan-bridge-wrapper.sh`; replace every
absolute placeholder. Put secrets in `~/.config/stackchan-hermes/bridge.env` with mode 0600, not in
the plist. Create the configured log directory first. `KeepAlive` restarts failures and
`ThrottleInterval=10` bounds restart loops. Bridge can start before Hermes; readiness recovers when
the public Hermes health/capability surfaces become available.
