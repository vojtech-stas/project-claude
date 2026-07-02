#!/usr/bin/env bash
# tools/dashboard-up.sh — thin wrapper delegating to tools/dashboard-up.ps1 (#1053).
#
# Convenience entry point for bash shells (Git Bash on Windows). Forwards all
# arguments (e.g. -CheckOnly) to the PowerShell script. Requires `powershell`
# on PATH; exits 1 with a warning if unavailable.
#
# USAGE:
#   bash tools/dashboard-up.sh [-CheckOnly]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PS1_SCRIPT="$SCRIPT_DIR/dashboard-up.ps1"

if ! command -v powershell >/dev/null 2>&1; then
  echo "[dashboard-up] ERROR: powershell not found on PATH — cannot run dashboard-up.ps1" >&2
  exit 1
fi

exec powershell -NoProfile -File "$PS1_SCRIPT" "$@"
