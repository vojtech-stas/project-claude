#!/usr/bin/env bash
# tools/restart-dashboard.sh — kill the 127.0.0.1:8765 listener and respawn dashboard/server.py.
#
# Reusable helper called by:
#   - .claude/hooks/dashboard-autostart.sh (stale-restart path, #846 defect 1)
#   - Manually: bash tools/restart-dashboard.sh (post-merge green step)
#
# Windows-correctness (runs in git-bash on Windows):
#   - lsof is NOT available on Windows; use `netstat -ano` to find the PID.
#   - Kill via `taskkill //F //PID <pid>` (Windows) with POSIX kill -9 fallback.
#   - Both branches (Windows + POSIX) must actually terminate the process, not just
#     attempt it — otherwise the respawn binds to a busy port.
#
# USAGE:
#   bash tools/restart-dashboard.sh [<server.py path>]
#
# Arguments:
#   $1  (optional) path to dashboard/server.py; defaults to
#       <repo_root>/dashboard/server.py discovered via git-common-dir.
#
# Soft-degrade guards (mirrors dashboard-autostart.sh):
#   - python3/python absent → warn and exit 1
#   - SERVER_SCRIPT not found → warn and exit 1
#   - kill fails → warn but still attempt respawn

set -uo pipefail

PORT=8765

# ---- Resolve repo root -------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT=""
_COMMON=$(git -C "$SCRIPT_DIR" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
if [ -n "$_COMMON" ]; then
  REPO_ROOT=$(dirname "$_COMMON")
fi
if [ -z "$REPO_ROOT" ] || [ ! -d "$REPO_ROOT" ]; then
  REPO_ROOT="${CLAUDE_PROJECT_DIR:-$SCRIPT_DIR/..}"
fi
REPO_ROOT="${REPO_ROOT//\\//}"  # normalize Windows backslashes

# ---- Resolve dashboard server script -----------------------------------------
if [ -n "${1:-}" ]; then
  SERVER_SCRIPT="${1//\\//}"
else
  SERVER_SCRIPT="$REPO_ROOT/dashboard/server.py"
fi

warn() { echo "[restart-dashboard] WARNING: $*" >&2; }

if [ ! -f "$SERVER_SCRIPT" ]; then
  warn "dashboard/server.py not found at $SERVER_SCRIPT"
  exit 1
fi

# ---- Resolve python interpreter ----------------------------------------------
PYTHON=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON="python"
else
  warn "python3/python not found — cannot respawn dashboard"
  exit 1
fi

# ---- Kill the existing listener on port $PORT --------------------------------
# Windows-compatible path: netstat -ano to find PID, taskkill to kill.
# POSIX fallback: lsof -ti:$PORT | xargs kill -9.
echo "[restart-dashboard] killing listener on port $PORT..." >&2

KILLED=0

# Windows path: netstat -ano (available in git-bash via Windows System32).
if command -v netstat >/dev/null 2>&1; then
  # netstat -ano output format:
  #   TCP    127.0.0.1:8765   0.0.0.0:0   LISTENING   <PID>
  # We extract the PID from the last field of any LISTENING line on :$PORT.
  PID=$(netstat -ano 2>/dev/null \
    | awk -v port=":$PORT" '$2 ~ port && $4 == "LISTENING" { print $5 }' \
    | head -1)

  if [ -n "$PID" ] && [ "$PID" != "0" ]; then
    echo "[restart-dashboard] found PID $PID via netstat; killing with taskkill..." >&2
    if command -v taskkill >/dev/null 2>&1; then
      taskkill //F //PID "$PID" >/dev/null 2>&1 && KILLED=1 || \
        warn "taskkill failed for PID $PID; will still attempt respawn"
    else
      # taskkill not in PATH but we're on Windows — try via cmd.exe
      cmd.exe //C "taskkill /F /PID $PID" >/dev/null 2>&1 && KILLED=1 || \
        warn "cmd.exe taskkill failed for PID $PID; will still attempt respawn"
    fi
  fi
fi

# POSIX fallback (Linux/macOS): lsof if netstat didn't kill.
if [ "$KILLED" -eq 0 ] && command -v lsof >/dev/null 2>&1; then
  POSIX_PIDS=$(lsof -ti:"$PORT" 2>/dev/null || true)
  if [ -n "$POSIX_PIDS" ]; then
    echo "[restart-dashboard] found PID(s) $POSIX_PIDS via lsof; sending SIGKILL..." >&2
    # shellcheck disable=SC2086
    kill -9 $POSIX_PIDS 2>/dev/null && KILLED=1 || \
      warn "kill -9 failed for PID(s) $POSIX_PIDS; will still attempt respawn"
  fi
fi

if [ "$KILLED" -eq 0 ]; then
  # No listener found or kill not needed — port may already be free.
  echo "[restart-dashboard] no listener found on port $PORT (or kill not needed)" >&2
fi

# Give the OS a moment to release the port.
sleep 1

# ---- Respawn dashboard server ------------------------------------------------
echo "[restart-dashboard] spawning $PYTHON $SERVER_SCRIPT ..." >&2
nohup "$PYTHON" "$SERVER_SCRIPT" >/dev/null 2>&1 &
disown $! 2>/dev/null || true

echo "[restart-dashboard] done. Dashboard respawning on port $PORT." >&2
exit 0
