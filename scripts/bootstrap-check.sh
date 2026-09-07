#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is required. See docs/operations.md for installation guidance." >&2
  exit 2
fi

uv run --locked stackchan-bridge doctor --offline "$@"
