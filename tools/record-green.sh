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
#   RECORD_GREEN_GH_CMD      — command run instead of 'gh'; must print the
#                              ci conclusion string to stdout (e.g. "success").
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

# --- 2a. Verify GitHub ci conclusion ---
echo "INFO: checking GitHub ci conclusion for $DEV_SHA ..."
if [ -n "${RECORD_GREEN_GH_CMD:-}" ]; then
  # Test injection: run the stub command.
  CI_CONCLUSION="$(eval "$RECORD_GREEN_GH_CMD" 2>/dev/null || true)"
else
  # Real path: find the PR whose head is $DEV_SHA, then read the ci check run.
  # Use gh api to get check runs for the commit on the develop branch.
  CI_CONCLUSION="$(
    gh api \
      "repos/{owner}/{repo}/commits/$DEV_SHA/check-runs" \
      --jq '.check_runs[] | select(.name == "ci") | .conclusion' \
      2>/dev/null | tail -1 || true
  )"
fi

if [ "$CI_CONCLUSION" != "success" ]; then
  echo "ERROR: GitHub ci conclusion for develop HEAD is '$CI_CONCLUSION' (need 'success')" >&2
  echo "ERROR: develop is NOT green — refusing to record develop_green (no false-green)" >&2
  exit 1
fi
echo "INFO: GitHub ci conclusion = $CI_CONCLUSION — OK"

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
