#!/bin/bash
# worktree-guard.sh — post-dispatch worktree leak-guard + root ff-sync (ADR-0041 D1/D3).
#
# CONTRACT: Orchestrator-invoked via Bash after each isolated Agent dispatch.
#   NOT a Claude Code event hook (per ADR-0015). Two modes (mode as $1):
#
#   branch-restore <expected-branch>
#     git fetch origin main (soft-degrade on failure); if the current worktree
#     drifted off <expected-branch> AND the tree is clean, ff-restores via
#     `git checkout -B <expected> origin/main`. No-op if dirty or already correct.
#     Enforces the ADR-0036 D3 invariant ("dispatched subagents never mutate the
#     orchestrator's session worktree") by asserting + restoring after each dispatch.
#
#   root-sync
#     Resolves the root repo via `git --git-common-dir` → dirname (same pattern as
#     .claude/hooks/log-event.sh). If the root tree is clean, ff-syncs to origin/main:
#     `git -C <root> checkout main && git -C <root> merge --ff-only origin/main`.
#     STRICT: ff-only, clean-only, soft-degrade on any error. Never reset/force/non-ff.
#     Implements ADR-0041 D3 carve-out: orchestrator MAY ff-sync root post-merge.
#
# SOFT-DEGRADE: every failure path exits 0. A broken guard must never break /ship.
# Mirror the bare-|| true / 2>/dev/null soft-degrade idioms from log-event.sh.

MODE="$1"

case "$MODE" in
  branch-restore)
    EXPECTED="$2"
    if [ -z "$EXPECTED" ]; then
      exit 0
    fi

    git fetch origin main 2>/dev/null || true

    CURRENT=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) || exit 0
    if [ "$CURRENT" = "$EXPECTED" ]; then
      exit 0
    fi

    # Only restore when the tree is clean (no uncommitted orchestrator work).
    DIRTY=$(git status --porcelain --untracked-files=no 2>/dev/null)
    if [ -n "$DIRTY" ]; then
      exit 0
    fi

    git checkout -B "$EXPECTED" origin/main 2>/dev/null || true
    exit 0
    ;;

  root-sync)
    # Resolve the root repo via git --git-common-dir (canonical pattern from log-event.sh).
    ROOT="${CLAUDE_PROJECT_DIR:-.}"
    COMMON=$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
    if [ -n "$COMMON" ]; then
      MAIN=$(dirname "$COMMON")
    else
      MAIN="$ROOT"
    fi
    [ -d "$MAIN" ] || exit 0

    # Only ff-sync when the root tree is clean.
    DIRTY=$(git -C "$MAIN" status --porcelain --untracked-files=no 2>/dev/null)
    if [ -n "$DIRTY" ]; then
      exit 0
    fi

    git -C "$MAIN" fetch origin main 2>/dev/null || true
    git -C "$MAIN" checkout main 2>/dev/null || true
    git -C "$MAIN" merge --ff-only origin/main 2>/dev/null || true
    exit 0
    ;;

  *)
    # Unknown mode — soft-degrade.
    exit 0
    ;;
esac
