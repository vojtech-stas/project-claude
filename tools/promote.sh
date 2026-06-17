#!/bin/bash
# promote.sh — fast-forward develop HEAD into main + record promotion event.
#
# USAGE:
#   bash tools/promote.sh
#
# What it does (ADR-0070 D3):
#   1. Resolves develop HEAD sha.
#   2. Verifies the fast-forward condition: main must be an ancestor of develop.
#      If not, aborts — promotion is ff-only (linear history invariant).
#   3. Pushes develop HEAD to main on origin (ff-only via --force-with-lease
#      + merge=ff pre-check).
#   4. Appends one {"v":2,"event":"promotion",...} line to
#      .claude/logs/workflow-events.jsonl (creates the file if absent).
#
# Idempotent-safe: if main already equals develop HEAD, records the event and
# exits 0 (no-op push, honest log entry).
#
# Run by the ORCHESTRATOR post-merge; NOT by the implementer.
# This script only gets committed here — the orchestrator invokes it.
#
# Requires: git, date (ISO-8601), GITHUB_TOKEN or gh auth (for push).

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
EVENTS_LOG="$REPO_ROOT/.claude/logs/workflow-events.jsonl"

# --- 0. RELEASE-READY pre-flight guard (slice #838 / ADR-0070 D2) ---
# Refuse to promote unless the six-condition gate reports verdict=true.
# The gate exits 0 regardless (WARN = held is not a script error); we parse
# the verdict field from the JSON output.
echo "INFO: checking RELEASE-READY gate..."
RELEASE_READY_OUT="$(python3 "$REPO_ROOT/dashboard/health.py" --check RELEASE-READY 2>&1)" || true
# Extract verdict from JSON output (last line starting with '{')
VERDICT="$(echo "$RELEASE_READY_OUT" | python3 -c "
import sys, json
for line in reversed(sys.stdin.read().splitlines()):
    line = line.strip()
    if line.startswith('{'):
        try:
            d = json.loads(line)
            print(d.get('verdict', ''))
            sys.exit(0)
        except Exception:
            pass
print('')
" 2>/dev/null || echo "")"

if [ "$VERDICT" != "true" ]; then
  # Extract detail for a helpful error message
  DETAIL="$(echo "$RELEASE_READY_OUT" | python3 -c "
import sys, json
for line in reversed(sys.stdin.read().splitlines()):
    line = line.strip()
    if line.startswith('{'):
        try:
            d = json.loads(line)
            print(d.get('detail', 'gate not ready'))
            sys.exit(0)
        except Exception:
            pass
print('gate not ready (could not parse RELEASE-READY output)')
" 2>/dev/null || echo "gate not ready")"
  echo "ERROR: RELEASE-READY gate is not open — promotion refused" >&2
  echo "ERROR: $DETAIL" >&2
  echo "INFO: Resolve all failing conditions before promoting develop → main." >&2
  exit 1
fi
echo "INFO: RELEASE-READY gate: $VERDICT — proceeding with promotion"

# --- 0b. Human-ack sentinel gate (slice #881, fixes #880 bypass) ---
# Require a human-created sentinel file .claude/PROMOTE_OK in the repo root.
# Subagent worktrees check out only tracked files — this file is gitignored,
# so it can never exist in a subagent context, structurally blocking bypasses.
SENTINEL="$REPO_ROOT/.claude/PROMOTE_OK"
if [ ! -f "$SENTINEL" ]; then
  echo "PROMOTION REFUSED: human ack required — create .claude/PROMOTE_OK to authorize" >&2
  echo "INFO: This sentinel is gitignored; it must be created manually by a human." >&2
  echo "INFO: It is deleted automatically after a successful promotion (one-shot)." >&2
  exit 1
fi
echo "INFO: human-ack sentinel found — proceeding with promotion"

# --- 1. Resolve develop HEAD sha ---
DEVELOP_SHA="$(git rev-parse origin/develop 2>/dev/null || git rev-parse develop 2>/dev/null)" || {
  echo "ERROR: cannot resolve develop HEAD — branch does not exist yet" >&2
  exit 1
}

# --- 2. Verify fast-forward condition ---
MAIN_SHA="$(git rev-parse origin/main 2>/dev/null || git rev-parse main 2>/dev/null)" || {
  echo "ERROR: cannot resolve main HEAD" >&2
  exit 1
}

if [ "$MAIN_SHA" = "$DEVELOP_SHA" ]; then
  echo "INFO: main already equals develop HEAD ($DEVELOP_SHA) — idempotent no-op push"
else
  # main must be an ancestor of develop (ff-only check)
  if ! git merge-base --is-ancestor "$MAIN_SHA" "$DEVELOP_SHA" 2>/dev/null; then
    echo "ERROR: main ($MAIN_SHA) is NOT an ancestor of develop ($DEVELOP_SHA)" >&2
    echo "ERROR: cannot fast-forward; promotion aborted (linear history invariant)" >&2
    exit 1
  fi

  # --- 3. Fast-forward push ---
  echo "INFO: fast-forwarding main to develop HEAD $DEVELOP_SHA"
  git push origin "refs/remotes/origin/develop:refs/heads/main" --force-with-lease="refs/heads/main:$MAIN_SHA"
  echo "INFO: push complete"
fi

# --- 3b. Remove human-ack sentinel (one-shot: fresh ack required per promotion) ---
rm -f "$SENTINEL"
echo "INFO: human-ack sentinel removed — next promotion requires a fresh .claude/PROMOTE_OK"

# --- 4. Append promotion event ---
TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || python3 -c "from datetime import datetime,timezone; print(datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))")"
SESSION_ID="${CLAUDE_SESSION_ID:-orchestrator}"

mkdir -p "$(dirname "$EVENTS_LOG")"
EVENT="{\"v\":2,\"ts\":\"$TS\",\"session_id\":\"$SESSION_ID\",\"src\":\"orchestrator\",\"event\":\"promotion\",\"from\":\"develop\",\"to\":\"main\",\"sha\":\"$DEVELOP_SHA\"}"
echo "$EVENT" >> "$EVENTS_LOG"
echo "INFO: promotion event appended — sha=$DEVELOP_SHA ts=$TS"
