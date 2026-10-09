#!/usr/bin/env bash
# Single quality gate, shared by the pre-commit hook, CI and the Claude Code Stop hook.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
