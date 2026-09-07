#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

uv run pytest -q \
  simulator/tests/test_bridge_integration.py \
  simulator/tests/test_voice_flow.py \
  simulator/tests/test_reconnect.py
