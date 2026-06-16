#!/usr/bin/env bash
# .claude/hooks/dashboard-autostart.sh — SessionStart tooling-spawn hook
#
# Spawns dashboard/server.py if not already running on 127.0.0.1:8765.
# Authorized by ADR-0033 D1 (tooling-spawn carveout). All 4 criteria met:
#   1. No LLM API calls (no LLM SDK, no gh-copilot, no model endpoint invocation)
#   2. Localhost-only (server.py binds localhost per slice 1)
#   3. Project-scoped ($CLAUDE_PROJECT_DIR/dashboard/server.py)
#   4. Idempotent (curl-check before spawn — exits 0 if already up AND sha matches)
#
# #846 defect 1 fix: when a server is already up, additionally query /api/meta
# and compare its sha to the current HEAD (via MAIN_ROOT from lib-root.sh).
# If stale (sha differs), kill the old listener and respawn from current code via
# tools/restart-dashboard.sh.  If sha matches, exit 0 as before.

set -euo pipefail

# Resolve main root + LOG_DIR via lib-root.sh (PRD #668 beacon unification).
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
# shellcheck source=lib-root.sh
source "$SCRIPT_DIR/lib-root.sh"

printf '{"hook":"dashboard-autostart","ts":"%s"}\n' "$(date -u -Iseconds 2>/dev/null)" >> "$LOG_DIR/hook-fires.jsonl" 2>/dev/null || true

# --- Soft-degrade helpers ---
warn() { echo "[dashboard-autostart] WARNING: $*" >&2; }

# Require curl; soft-degrade if missing
if ! command -v curl >/dev/null 2>&1; then
  warn "curl not found — cannot check if dashboard is running; skipping auto-start"
  exit 0
fi

# Resolve python interpreter: python3 preferred, python fallback (Windows Git Bash)
PYTHON=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON="python"
else
  warn "python3/python not found — cannot start dashboard; skipping"
  exit 0
fi

# Normalize $CLAUDE_PROJECT_DIR: convert Windows backslashes to forward slashes
PROJECT_DIR="${CLAUDE_PROJECT_DIR//\\//}"

if [ -z "$PROJECT_DIR" ]; then
  warn "CLAUDE_PROJECT_DIR is not set — cannot locate dashboard/server.py; skipping"
  exit 0
fi

SERVER_SCRIPT="$PROJECT_DIR/dashboard/server.py"

if [ ! -f "$SERVER_SCRIPT" ]; then
  warn "dashboard/server.py not found at $SERVER_SCRIPT — skipping auto-start"
  exit 0
fi

# Resolve restart helper (tools/restart-dashboard.sh in the main repo root).
RESTART_HELPER="$MAIN_ROOT/tools/restart-dashboard.sh"

# --- Idempotency check (ADR-0033 D1.4): is the server already up on 127.0.0.1:8765? ---
HTTP_STATUS=$(curl -s -o /dev/null -w '%{http_code}' --max-time 1 http://127.0.0.1:8765/api/architecture 2>/dev/null || echo "000")

if [ "$HTTP_STATUS" = "200" ]; then
  # Server is up — check if it's serving current code (#846 defect 1).
  # Query /api/meta for the sha the running server captured at startup.
  SERVER_SHA=$(curl -s --max-time 2 http://127.0.0.1:8765/api/meta 2>/dev/null \
    | "$PYTHON" -c "import sys,json; d=json.load(sys.stdin); print(d.get('sha',''))" \
    2>/dev/null || echo "")

  # Get the current HEAD sha of the main repo.
  HEAD_SHA=$(git -C "$MAIN_ROOT" rev-parse HEAD 2>/dev/null || echo "")

  if [ -n "$SERVER_SHA" ] && [ -n "$HEAD_SHA" ] && [ "$SERVER_SHA" = "$HEAD_SHA" ]; then
    # Sha matches — server is current; nothing to do.
    exit 0
  fi

  # Sha mismatch (or couldn't read sha) → stale server; restart from current code.
  if [ -n "$SERVER_SHA" ] && [ -n "$HEAD_SHA" ]; then
    warn "stale server detected (server sha: ${SERVER_SHA:0:8}, HEAD: ${HEAD_SHA:0:8}); restarting..."
  else
    warn "could not verify server sha; restarting to ensure current code is served..."
  fi

  if [ -f "$RESTART_HELPER" ]; then
    bash "$RESTART_HELPER" "$SERVER_SCRIPT" >&2 || warn "restart-dashboard.sh failed; server may be stale"
  else
    warn "restart-dashboard.sh not found at $RESTART_HELPER — cannot auto-restart stale server"
  fi
  exit 0
fi

# --- Spawn dashboard server (ADR-0033 D1.3: project-scoped, localhost-only) ---
# nohup + disown detaches from the parent shell's job table (works on Linux/macOS/Git Bash)
nohup "$PYTHON" "$SERVER_SCRIPT" >/dev/null 2>&1 &
disown $! 2>/dev/null || true

exit 0
