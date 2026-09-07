#!/bin/sh
set -eu

project_dir="/ABSOLUTE/PATH/stackchan-hermes"
environment_file="${HOME}/.config/stackchan-hermes/bridge.env"
config_file="${HOME}/.config/stackchan-hermes/config.toml"

if [ ! -r "$environment_file" ] || [ ! -r "$config_file" ]; then
  echo "StackChan Bridge environment or config file is unavailable" >&2
  exit 2
fi

set -a
. "$environment_file"
set +a
cd "$project_dir"
exec uv run stackchan-bridge serve --config "$config_file"
