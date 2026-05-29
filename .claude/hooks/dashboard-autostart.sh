#!/usr/bin/env bash
# .claude/hooks/dashboard-autostart.sh — SessionStart tooling-spawn hook
#
# Spawns dashboard/server.py if not already running on localhost:8765.
# Authorized by ADR-0033 D1 (tooling-spawn carveout). All 4 criteria met:
#   1. No LLM API calls (no LLM SDK, no gh-copilot, no model endpoint invocation)
#   2. Localhost-only (server.py binds localhost per slice 1)
#   3. Project-scoped ($CLAUDE_PROJECT_DIR/dashboard/server.py)
#   4. Idempotent (curl-check before spawn — exits 0 if already up)

set -euo pipefail

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

# --- Idempotency check (ADR-0033 D1.4): is the server already up on localhost:8765? ---
HTTP_STATUS=$(curl -s -o /dev/null -w '%{http_code}' --max-time 1 http://localhost:8765/api/architecture 2>/dev/null || echo "000")

if [ "$HTTP_STATUS" = "200" ]; then
  # Dashboard already running — nothing to do
  exit 0
fi

# --- Spawn dashboard server (ADR-0033 D1.3: project-scoped, localhost-only) ---
# nohup + disown detaches from the parent shell's job table (works on Linux/macOS/Git Bash)
nohup "$PYTHON" "$SERVER_SCRIPT" >/dev/null 2>&1 &
disown $! 2>/dev/null || true

exit 0
