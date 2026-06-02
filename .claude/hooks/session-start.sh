#!/bin/bash
# SessionStart hook for Claude Code on the web.
#
# Installs the project's Python dependencies (including pytest and ruff, which
# are pinned in requirements.txt) into the system interpreter so that
# `python -m pytest` and `python -m ruff` resolve both the test/lint tools and
# the project libraries (pandas, numpy, scipy, ...) from a single environment.
#
# Note: the pre-provisioned `pytest`/`ruff` shims on PATH are isolated uv tools
# that cannot see project libraries, so always invoke them via `python -m`.
set -euo pipefail

# Only run in the remote (Claude Code on the web) environment.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# Make the repo root importable so `from src.screener import ...` works.
echo 'export PYTHONPATH="$CLAUDE_PROJECT_DIR"' >> "$CLAUDE_ENV_FILE"

# Idempotent: pip skips already-satisfied packages on re-runs.
python -m pip install --quiet --disable-pip-version-check --root-user-action=ignore -r requirements.txt
