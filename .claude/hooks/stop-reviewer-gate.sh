#!/bin/bash
# Stop event hook — block session-stop if in-flight PR lacks reviewer subagent APPROVE per ADR-0029.
# Reads Stop event JSON on stdin; checks gh pr list --author @me; greps for "VERDICT: APPROVE" in comments.
# Soft-degrades if jq/gh missing; respects STOP_GATE_BYPASS=1 override; skips subagent context.
# ADR-0057 D2 retrofit: reads stdin, honors stop_hook_active immediately; on gh/infra failure
# allows the stop AND emits ERROR beacon (fail-open + fail-loud).
# #846: added emit_ok_beacon at every non-error success terminal path so HOOK-INTEGRITY
# no longer false-flags stop-reviewer-gate as dead (was: 0/N ratio).
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || true

# Resolve main root + LOG_DIR via lib-root.sh (PRD #668 beacon unification).
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
# shellcheck source=lib-root.sh
source "$SCRIPT_DIR/lib-root.sh"

# Step 1: read full stdin once (ADR-0057 D2 — must read stdin to honor stop_hook_active).
_SRG_STDIN=$(cat)

# Step 2: emit attempt beacon BEFORE any logic (ADR-0057 D1a).
_BEACON_DIR="${WORKFLOW_LOG_DIR:-$LOG_DIR}"
mkdir -p "$_BEACON_DIR" 2>/dev/null || true
printf '{"hook":"stop-reviewer-gate","status":"attempt","ts":"%s"}\n' \
  "$(date -u -Iseconds 2>/dev/null)" \
  >> "$_BEACON_DIR/hook-fires.jsonl" 2>/dev/null || true

# Step 2b: emit session_stop workflow event (PRD #876 consolidation).
# Replaces the standalone settings.json Stop log-tool-event.sh entry.
# Fires unconditionally here (before gate logic) so the event is always recorded,
# even when the gate blocks the session (exit 2 path).
printf '%s' "$_SRG_STDIN" | bash "$SCRIPT_DIR/log-tool-event.sh" session_stop 2>/dev/null || true

# Step 3: extract stop_hook_active + session_id from stdin (ADR-0057 D2 — loop guard first).
_SRG_ACTIVE=$(printf '%s' "$_SRG_STDIN" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(str(d.get('stop_hook_active',False)).lower())" \
  2>/dev/null || echo "false")
_SRG_SID=$(printf '%s' "$_SRG_STDIN" | python3 -c \
  "import sys,json; print(json.load(sys.stdin).get('session_id',''))" \
  2>/dev/null || echo "")

# --- Beacon helpers (defined before first call site) ---

# emit_ok_beacon: emit ok beacon at every non-error success terminal path (#846 defect 2).
# Fixes HOOK-INTEGRITY false-positive (was emitting attempt but never ok).
emit_ok_beacon() {
  printf '{"hook":"stop-reviewer-gate","status":"ok","ts":"%s","session_id":"%s"}\n' \
    "$(date -u -Iseconds 2>/dev/null)" "$_SRG_SID" \
    >> "$_BEACON_DIR/hook-fires.jsonl" 2>/dev/null || true
  exit 0
}

# emit_error_beacon: allow the stop + emit ERROR beacon (ADR-0057 D1b/D2 fail-open).
emit_error_beacon() {
  local reason="$1"
  printf '{"hook":"stop-reviewer-gate","status":"ERROR","ts":"%s","session_id":"%s","reason":"%s"}\n' \
    "$(date -u -Iseconds 2>/dev/null)" "$_SRG_SID" "$reason" \
    >> "$_BEACON_DIR/hook-fires.jsonl" 2>/dev/null || true
  exit 0
}

# --- Guard paths ---

if [ "$_SRG_ACTIVE" = "true" ]; then
  # ADR-0057 D2: stop_hook_active → exit 0 immediately (loop guard; no blocking allowed).
  emit_ok_beacon
fi

# Skip subagent context — reviewer subagent's own Stop must not trigger loop.
if [ -n "${CLAUDE_AGENT_TYPE:-}" ]; then
  emit_ok_beacon
fi

# Bypass override per ADR-0029 D2.
if [ "${STOP_GATE_BYPASS:-}" = "1" ]; then
  echo "stop-reviewer-gate: bypass via STOP_GATE_BYPASS=1" >&2
  emit_ok_beacon
fi

# Soft-degrade if gh or jq missing (per ADR-0029 D3) — fail-open + ERROR beacon.
if ! command -v gh >/dev/null 2>&1; then
  emit_error_beacon "gh-missing"
fi
if ! command -v jq >/dev/null 2>&1; then
  emit_error_beacon "jq-missing"
fi

# Fetch in-flight PRs authored by current user.
PRS=$(gh pr list --author @me --state open --json number 2>/dev/null | jq -r '.[].number' 2>/dev/null) || \
  emit_error_beacon "gh-pr-list-failed"
if [ -z "$PRS" ]; then
  emit_ok_beacon  # no in-flight PRs — nothing to check
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

emit_ok_beacon  # all in-flight PRs have reviewer APPROVE
