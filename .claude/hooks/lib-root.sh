#!/bin/bash
# lib-root.sh — resolve the MAIN repo root via git-common-dir (the proven
# pattern from log-event.sh).  Source this file; it sets MAIN_ROOT and
# LOG_DIR, then mkdir -p's the logs directory.
#
# Works in both the main worktree and any linked worktree:
#   git rev-parse --path-format=absolute --git-common-dir
#   → <main-repo>/.git   in all cases
#   → dirname → <main-repo>
#
# SOFT-DEGRADE: if git resolution fails, fall back to $CLAUDE_PROJECT_DIR.
# Never exits non-zero.  Caller gets a writable LOG_DIR or the fallback.

REPO_ROOT="${CLAUDE_PROJECT_DIR:-.}"
_COMMON=$(git -C "$REPO_ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
if [ -n "$_COMMON" ]; then
  MAIN_ROOT=$(dirname "$_COMMON")
else
  MAIN_ROOT="$REPO_ROOT"
fi
[ -d "$MAIN_ROOT" ] || MAIN_ROOT="$REPO_ROOT"

LOG_DIR="$MAIN_ROOT/.claude/logs"
mkdir -p "$LOG_DIR" 2>/dev/null || true

# ---------------------------------------------------------------------------
# dashboard_probe_identity — shared identity-verifying liveness probe
# (slice #1189, root-cause #1184: a foreign listener squatting the dashboard
# port fooled three separate probes three different ways on 2026-08-20).
#
# GET <base_url>/api/meta and require parseable JSON with a non-empty "sha"
# field. Wrong payload (non-200 status, non-JSON body, or missing "sha") is
# classified OCCUPIED — something answered but it is not our dashboard —
# and is NEVER conflated with "no server running".
#
# Usage: dashboard_probe_identity <python_bin> <base_url> [timeout_secs]
# Prints exactly one line to stdout:
#   "ok <sha>"            — verified as our dashboard; <sha> is its /api/meta sha
#   "occupied <detail>"   — something answered but failed the identity check
#   "no-server"           — connection failed; nothing answered at all
# ---------------------------------------------------------------------------
dashboard_probe_identity() {
  local py="$1" base_url="$2" timeout="${3:-2}"
  local http_status body sha

  # curl's -w '%{http_code}' already prints "000" on a connection failure —
  # only fall back when the whole invocation produced no output at all.
  http_status=$(curl -s -o /dev/null -w '%{http_code}' --max-time "$timeout" \
    "$base_url/api/meta" 2>/dev/null)
  [ -z "$http_status" ] && http_status="000"

  if [ "$http_status" = "000" ]; then
    echo "no-server"
    return 0
  fi

  if [ "$http_status" != "200" ]; then
    echo "occupied HTTP $http_status on /api/meta (not project-claude dashboard)"
    return 0
  fi

  body=$(curl -s --max-time "$timeout" "$base_url/api/meta" 2>/dev/null || echo "")
  sha=$(printf '%s' "$body" | "$py" -c "
import sys, json
try:
    d = json.load(sys.stdin)
    s = d.get('sha', '')
    print(s if s else '')
except Exception:
    print('')
" 2>/dev/null || echo "")

  if [ -z "$sha" ]; then
    echo "occupied non-conforming /api/meta JSON payload (no sha field)"
    return 0
  fi

  echo "ok $sha"
}
