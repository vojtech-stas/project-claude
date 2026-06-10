#!/bin/bash
# Stop event hook — block session-stop if in-flight PR lacks reviewer subagent APPROVE per ADR-0029.
# Reads Stop event JSON on stdin; checks gh pr list --author @me; greps for "VERDICT: APPROVE" in comments.
# Soft-degrades if jq/gh missing; respects STOP_GATE_BYPASS=1 override; skips subagent context.
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || true

# Resolve main root + LOG_DIR via lib-root.sh (PRD #668 beacon unification).
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
# shellcheck source=lib-root.sh
source "$SCRIPT_DIR/lib-root.sh"

printf '{"hook":"stop-reviewer-gate","ts":"%s"}\n' "$(date -Iseconds 2>/dev/null)" >> "$LOG_DIR/hook-fires.jsonl" 2>/dev/null || true

# Skip subagent context — reviewer subagent's own Stop must not trigger loop.
if [ -n "${CLAUDE_AGENT_TYPE:-}" ]; then
  exit 0
fi

# Bypass override per ADR-0029 D2.
if [ "${STOP_GATE_BYPASS:-}" = "1" ]; then
  echo "stop-reviewer-gate: bypass via STOP_GATE_BYPASS=1" >&2
  exit 0
fi

# Soft-degrade if gh or jq missing (per ADR-0029 D3) — fall through to existing logger.
if ! command -v gh >/dev/null 2>&1; then
  echo "stop-reviewer-gate: gh missing; soft-degrade exit 0" >&2
  exit 0
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "stop-reviewer-gate: jq missing; soft-degrade exit 0" >&2
  exit 0
fi

# Fetch in-flight PRs authored by current user.
PRS=$(gh pr list --author @me --state open --json number 2>/dev/null | jq -r '.[].number' 2>/dev/null)
if [ -z "$PRS" ]; then
  exit 0  # no in-flight PRs — nothing to check
fi

# For each PR, check for reviewer subagent VERDICT: APPROVE comment.
UNSIGNED=""
for N in $PRS; do
  APPROVED=$(gh pr view "$N" --json comments --jq '.comments | map(select(.body | test("VERDICT:\\s*APPROVE"))) | length' 2>/dev/null || echo 0)
  if [ "$APPROVED" -lt 1 ]; then
    UNSIGNED="$UNSIGNED #$N"
  fi
done

if [ -n "$UNSIGNED" ]; then
  echo "stop-reviewer-gate: in-flight PR(s) lacking reviewer subagent VERDICT: APPROVE:$UNSIGNED" >&2
  echo "stop-reviewer-gate: dispatch reviewer subagent before declaring done, OR set STOP_GATE_BYPASS=1 if reviewing manually." >&2
  exit 2
fi

exit 0
