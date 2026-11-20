#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

uv lock --check
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy bridge/src simulator/src
uv run --locked pytest -q --cov=stackchan_bridge --cov=stackchan_simulator --cov-report=term-missing \
  --cov-fail-under=85
uv run --locked python scripts/validate-protocol.py
uv run --locked python scripts/check-secrets.py
audit_cache_dir="${STACKCHAN_PIP_AUDIT_CACHE_DIR:-.local/cache/pip-audit}"
audit_dir="$(mktemp -d)"
trap 'rm -f -- "$audit_dir/pylock.toml"; rmdir -- "$audit_dir"' EXIT
uv export --locked --all-extras --all-groups --no-emit-project \
  --format pylock.toml --output-file "$audit_dir/pylock.toml" --quiet
uv run --locked pip-audit --locked --strict "$audit_dir" --cache-dir "$audit_cache_dir"
uv run --locked stackchan-bridge doctor --offline
