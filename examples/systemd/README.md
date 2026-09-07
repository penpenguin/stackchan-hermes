# systemd user-service example

Edit `stackchan-hermes-bridge.service` paths and install it under
`~/.config/systemd/user/`. Store secrets in the mode-0600 `EnvironmentFile`; never place values in
the unit. `Restart=on-failure`, `RestartSec=10` and start limits bound failure loops. The service
does not require Hermes ordering: `/health/ready` becomes healthy after Hermes starts. Before the
first start, create `~/.local/share/stackchan-hermes` and `~/.local/state/stackchan-hermes`; the unit
routes relative capture and debug-audio storage into those writable directories.
