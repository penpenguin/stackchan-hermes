#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy bridge/src simulator/src
uv run pytest -q --cov=stackchan_bridge --cov=stackchan_simulator --cov-report=term-missing \
  --cov-fail-under=85
uv run python scripts/validate-protocol.py
uv run python scripts/check-secrets.py
audit_cache_dir="${STACKCHAN_PIP_AUDIT_CACHE_DIR:-.local/cache/pip-audit}"
pip_cache_dir="${STACKCHAN_PIP_CACHE_DIR:-.local/cache/pip}"
PIP_CACHE_DIR="$pip_cache_dir" uv run pip-audit --cache-dir "$audit_cache_dir" --skip-editable
uv run stackchan-bridge doctor --offline
