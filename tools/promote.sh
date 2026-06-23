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

# REPO_ROOT: the worktree path (used only for locating dashboard/health.py,
# which is a tracked code file that lives in the worktree).
REPO_ROOT="$(git rev-parse --show-toplevel)"

# LOGROOT: the canonical root (git-common-dir parent).  When promote.sh runs
# from a worktree, REPO_ROOT is the worktree path but LOGROOT is the shared
# root.  The sentinel and events-log are untracked/gitignored files that must
# live at the CANONICAL root so they survive across worktrees.
# Fix for #1038: previously both used REPO_ROOT, so the sentinel placed at the
# canonical root was invisible when running from a worktree.
LOGROOT="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"

SENTINEL="$LOGROOT/.claude/PROMOTE_OK"
EVENTS_LOG="$LOGROOT/.claude/logs/workflow-events.jsonl"

# --- 0a. Human-ack sentinel gate (slice #881, fixes #880 bypass) ---
# Check the sentinel FIRST — before any gate check that could run pytest and
# wipe the sentinel.  Fix for #1038: old order ran RELEASE-READY gate first;
# the gate runs the full pytest suite, which includes tests that call
# promote.sh as a subprocess (in REPO_ROOT cwd); those sub-invocations delete
# .claude/PROMOTE_OK on the "proceed" path → outer promote.sh always refused.
#
# Sentinel is a human-created file at the canonical LOGROOT/.claude/PROMOTE_OK.
# Subagent worktrees check out only tracked files — this file is gitignored,
# so it can never exist in a subagent context, structurally blocking bypasses.
if [ ! -f "$SENTINEL" ]; then
  echo "PROMOTION REFUSED: human ack required — create .claude/PROMOTE_OK to authorize" >&2
  echo "INFO: This sentinel is gitignored; it must be created manually by a human." >&2
  echo "INFO: It is deleted automatically after a successful promotion (one-shot)." >&2
  exit 1
fi
echo "INFO: human-ack sentinel found — proceeding with promotion"

# --- 0b. RELEASE-READY pre-flight guard (slice #838 / ADR-0070 D2) ---
# Refuse to promote unless health.py --check RELEASE-READY emits a line
# matching `^PASS: RELEASE-READY`.  The CLI exits 0 for both PASS and WARN
# (ADR-0064 D3 — only FAIL exits non-zero), so we MUST grep the output text,
# not the exit code.  Fix for #1036: the old code parsed a JSON `verdict`
# field that the CLI never emits; the real contract is the PASS:/WARN: prefix.
#
# Injection: set PROMOTE_HEALTH_CMD to override the health.py invocation
# (used by tests to stub output without spawning the real CLI).
echo "INFO: checking RELEASE-READY gate..."
_DEFAULT_HEALTH_CMD="python3 $REPO_ROOT/dashboard/health.py --check RELEASE-READY"
_HEALTH_CMD="${PROMOTE_HEALTH_CMD:-$_DEFAULT_HEALTH_CMD}"
RELEASE_READY_OUT="$(eval "$_HEALTH_CMD" 2>&1)" || true

if printf '%s\n' "$RELEASE_READY_OUT" | grep -qE '^PASS: RELEASE-READY'; then
  echo "INFO: RELEASE-READY gate open — proceeding"
else
  echo "ERROR: RELEASE-READY gate not open — promotion refused" >&2
  echo "ERROR: $RELEASE_READY_OUT" >&2
  echo "INFO: Resolve all failing conditions before promoting develop → main." >&2
  exit 1
fi

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
  # _PROMOTE_SH_SKIP_PUSH=1 bypasses the real push (test isolation only).
  if [ "${_PROMOTE_SH_SKIP_PUSH:-}" = "1" ]; then
    echo "INFO: _PROMOTE_SH_SKIP_PUSH=1 — skipping real push (test mode)"
  else
    git push origin "refs/remotes/origin/develop:refs/heads/main" --force-with-lease="refs/heads/main:$MAIN_SHA"
  fi
  echo "INFO: push complete"
fi

# --- 3b. Remove human-ack sentinel (one-shot: fresh ack required per promotion) ---
# Uses rm -f: defensive even though sentinel is confirmed present above (e.g.
# if a concurrent process removed it between check and here, rm -f is safe).
rm -f "$SENTINEL"
echo "INFO: human-ack sentinel removed — next promotion requires a fresh .claude/PROMOTE_OK"

# --- 4. Append promotion event ---
TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || python3 -c "from datetime import datetime,timezone; print(datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))")"
SESSION_ID="${CLAUDE_SESSION_ID:-orchestrator}"

mkdir -p "$(dirname "$EVENTS_LOG")"
EVENT="{\"v\":2,\"ts\":\"$TS\",\"session_id\":\"$SESSION_ID\",\"src\":\"orchestrator\",\"event\":\"promotion\",\"from\":\"develop\",\"to\":\"main\",\"sha\":\"$DEVELOP_SHA\"}"
echo "$EVENT" >> "$EVENTS_LOG"
echo "INFO: promotion event appended — sha=$DEVELOP_SHA ts=$TS"
