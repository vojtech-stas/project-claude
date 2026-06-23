#!/bin/bash
# record-green.sh — verify develop is genuinely green, then record develop_green.
#
# USAGE:
#   bash tools/record-green.sh [--dry-run]
#
# What it does (slice #1032 / PRD #1031):
#   1. Resolves develop HEAD sha (git rev-parse origin/develop).
#   2. Verifies BOTH conditions:
#        (a) GitHub 'ci' check conclusion on develop HEAD sha == 'success'
#        (b) python -m pytest tests/ -q exit code == 0
#   3. On BOTH pass: appends exactly one {"v":2,"event":"develop_green",...} line
#      to the CANONICAL telemetry log (resolved via git-common-dir, not repo root)
#      so worktree runs write the shared root log (#1021 lesson).
#   4. On EITHER fail: prints reason to stderr, writes NOTHING, exits 1.
#      This is the core safety property: NEVER write a false green.
#
# --dry-run flag:
#   Runs both verifications + prints the event it WOULD write (or the failure
#   reason), but does NOT append to the log. Exits 0 if green, 1 if not.
#
# Test injection (env vars, consumed only when set):
#   RECORD_GREEN_CI_STATUS   — when set, treat this value as the CI status
#                              instead of calling _fetch_github_ci_conclusion.
#                              Accepted: pass | fail | pending | unavailable
#                              (takes priority over RECORD_GREEN_GH_CMD).
#   RECORD_GREEN_GH_CMD      — LEGACY: command run instead of 'gh'; must print
#                              the ci conclusion string to stdout ("success").
#                              Only used when RECORD_GREEN_CI_STATUS is unset.
#   RECORD_GREEN_PYTEST_CMD  — command run instead of 'python -m pytest tests/ -q';
#                              must exit 0 for pass, non-zero for fail.
#   RECORD_GREEN_TEST_LOG_PATH — when set, write to this path instead of the
#                                canonical git-common-dir log (test isolation).
#
# Run by the ORCHESTRATOR after develop PRs are merged and before promoting.
# Requires: git, gh (GitHub CLI), python -m pytest.

set -euo pipefail

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    *) echo "ERROR: unknown argument: $arg" >&2; exit 1 ;;
  esac
done

# --- 1. Resolve develop HEAD sha ---
DEV_SHA="$(git rev-parse origin/develop 2>/dev/null || git rev-parse develop 2>/dev/null)" || {
  echo "ERROR: cannot resolve develop HEAD — fetch origin first" >&2
  exit 1
}
echo "INFO: develop HEAD = $DEV_SHA"

# --- 2a. Verify GitHub ci conclusion via PR-mergeCommit lookup ---
# Squash-merge commits (every develop HEAD in the two-tier workflow) have NO
# check-runs attached to them — GitHub CI fires on the PR head, not the squash
# result.  We must find the PR whose mergeCommit.oid == develop HEAD and read
# THAT PR's ci check (the same strategy dashboard/health.py uses).
echo "INFO: checking GitHub ci conclusion for $DEV_SHA ..."
if [ -n "${RECORD_GREEN_CI_STATUS+x}" ]; then
  # Test injection (highest priority): RECORD_GREEN_CI_STATUS overrides everything
  # when the variable is SET (even to empty — empty means refuse, not skip).
  CI_STATUS="${RECORD_GREEN_CI_STATUS:-}"
  echo "INFO: CI status from RECORD_GREEN_CI_STATUS (test injection) = '$CI_STATUS'"
elif [ -n "${RECORD_GREEN_GH_CMD:-}" ]; then
  # Legacy test injection: RECORD_GREEN_GH_CMD echoes a raw conclusion string.
  # Map "success" → "pass" for consistency; anything else → refuse.
  RAW_CONCLUSION="$(eval "$RECORD_GREEN_GH_CMD" 2>/dev/null || true)"
  if [ "$RAW_CONCLUSION" = "success" ]; then
    CI_STATUS="pass"
  else
    CI_STATUS="$RAW_CONCLUSION"
  fi
  echo "INFO: CI status from RECORD_GREEN_GH_CMD (legacy injection) = '$CI_STATUS'"
else
  # Real path: delegate to dashboard/health.py::_fetch_github_ci_conclusion().
  # It finds the merged PR whose mergeCommit.oid == develop HEAD and reads
  # THAT PR's ci check — works correctly for squash-merge commits.
  # Use git show-toplevel (not git-common-dir) for the dashboard import so
  # worktree runs load the worktree's own health.py (which has the function),
  # not the root repo's potentially-older copy.
  SCRIPT_REPO_ROOT="$(git rev-parse --show-toplevel)"
  COMMON_LOGROOT="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
  CI_STATUS="$(python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_REPO_ROOT/dashboard')
from health import _fetch_github_ci_conclusion
status, detail = _fetch_github_ci_conclusion('$COMMON_LOGROOT')
print(status)
" 2>/dev/null || echo "unavailable")"
  echo "INFO: CI status from PR-mergeCommit lookup = '$CI_STATUS'"
fi

if [ "$CI_STATUS" != "pass" ]; then
  echo "ERROR: GitHub ci conclusion for develop HEAD is '$CI_STATUS' (need 'pass')" >&2
  echo "ERROR: develop is NOT green — refusing to record develop_green (no false-green)" >&2
  exit 1
fi
echo "INFO: GitHub ci = $CI_STATUS — OK"

# --- 2b. Verify pytest green ---
echo "INFO: running pytest to verify tests are green ..."
if [ -n "${RECORD_GREEN_PYTEST_CMD:-}" ]; then
  # Test injection: run the stub command.
  if ! eval "$RECORD_GREEN_PYTEST_CMD" >/dev/null 2>&1; then
    echo "ERROR: pytest (stub) exited non-zero — develop tests are NOT green" >&2
    echo "ERROR: refusing to record develop_green (no false-green)" >&2
    exit 1
  fi
else
  # Real path: run the full test suite.
  REPO_ROOT="$(git rev-parse --show-toplevel)"
  if ! python -m pytest "$REPO_ROOT/tests/" -q --no-header --tb=short 2>&1; then
    echo "ERROR: pytest exited non-zero — develop tests are NOT green" >&2
    echo "ERROR: refusing to record develop_green (no false-green)" >&2
    exit 1
  fi
fi
echo "INFO: pytest green — OK"

# --- 3. Build the event line ---
TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null \
  || python3 -c "from datetime import datetime,timezone; print(datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))")"
SESSION_ID="${CLAUDE_SESSION_ID:-orchestrator}"
EVENT="{\"v\":2,\"ts\":\"$TS\",\"session_id\":\"$SESSION_ID\",\"src\":\"orchestrator\",\"event\":\"develop_green\",\"sha\":\"$DEV_SHA\"}"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "INFO: --dry-run — would write:"
  echo "$EVENT"
  echo "INFO: --dry-run — nothing written"
  exit 0
fi

# --- 4. Resolve canonical log path via git-common-dir ---
# git-common-dir is the shared .git dir even in worktrees, so this always
# writes to the root repo's .claude/logs/ (not a worktree-local copy).
if [ -n "${RECORD_GREEN_TEST_LOG_PATH:-}" ]; then
  # Test isolation: write to the caller-specified path.
  EVENTS_LOG="$RECORD_GREEN_TEST_LOG_PATH"
else
  LOGROOT="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
  EVENTS_LOG="$LOGROOT/.claude/logs/workflow-events.jsonl"
fi

mkdir -p "$(dirname "$EVENTS_LOG")"

# --- 5. Append event ---
echo "$EVENT" >> "$EVENTS_LOG"
echo "INFO: develop_green event appended — sha=$DEV_SHA ts=$TS"
echo "INFO: log = $EVENTS_LOG"
