#!/bin/bash
# worktree-guard.sh — post-dispatch worktree leak-guard + root ff-sync (ADR-0041 D1/D3).
#
# CONTRACT: Orchestrator-invoked via Bash after each isolated Agent dispatch.
#   NOT a Claude Code event hook (per ADR-0015). Three modes (mode as $1):
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
#   prune
#     Resolves the root repo + the current/orchestrator worktree (skips BOTH — never
#     removes them). Iterates `git worktree list --porcelain`; for each remaining tree,
#     gets its branch and runs `git ls-remote --exit-code origin <branch>`. If the remote
#     branch is GONE (squash-merged + --delete-branch'd = work landed), removes the local
#     worktree via `git worktree unlock` + `git worktree remove --force`. Ends with
#     `git worktree prune` to clear stale dir-gone refs. Safety invariant: NEVER removes a
#     tree whose branch still exists on origin, the current/orchestrator session worktree,
#     or the root tree. When uncertain (no parseable branch, detached HEAD), leaves it.
#     Call after root-sync in /ship's post-merge step to self-clean landed worktrees.
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

  prune)
    # Resolve root repo (same git --git-common-dir pattern as root-sync).
    ROOT="${CLAUDE_PROJECT_DIR:-.}"
    COMMON=$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
    if [ -n "$COMMON" ]; then
      ROOT_PATH=$(dirname "$COMMON")
    else
      ROOT_PATH="$ROOT"
    fi

    # Resolve the current/orchestrator worktree.
    CURRENT_PATH=$(git rev-parse --show-toplevel 2>/dev/null) || CURRENT_PATH=""

    # Iterate worktrees via porcelain output, parsing worktree + branch lines.
    WORKTREE_PATH=""
    WORKTREE_BRANCH=""
    while IFS= read -r line; do
      case "$line" in
        "worktree "*)
          WORKTREE_PATH="${line#worktree }"
          WORKTREE_BRANCH=""
          ;;
        "branch refs/heads/"*)
          WORKTREE_BRANCH="${line#branch refs/heads/}"
          ;;
        "")
          # End of stanza — evaluate this worktree.
          if [ -n "$WORKTREE_PATH" ]; then
            # Skip root and current/orchestrator trees.
            if [ "$WORKTREE_PATH" = "$ROOT_PATH" ] || [ "$WORKTREE_PATH" = "$CURRENT_PATH" ]; then
              WORKTREE_PATH=""
              WORKTREE_BRANCH=""
              continue
            fi
            # When uncertain (no branch / detached HEAD), leave it.
            if [ -z "$WORKTREE_BRANCH" ]; then
              WORKTREE_PATH=""
              continue
            fi
            # Check whether the remote branch still exists.
            # ls-remote exits non-zero when the ref is absent → landed.
            if ! git ls-remote --exit-code origin "$WORKTREE_BRANCH" 2>/dev/null; then
              git worktree unlock "$WORKTREE_PATH" 2>/dev/null || true
              git worktree remove --force "$WORKTREE_PATH" 2>/dev/null || true
            fi
          fi
          WORKTREE_PATH=""
          WORKTREE_BRANCH=""
          ;;
      esac
    done < <(git worktree list --porcelain 2>/dev/null; echo "")

    # Clear stale dir-gone worktree refs.
    git worktree prune 2>/dev/null || true
    exit 0
    ;;

  *)
    # Unknown mode — soft-degrade.
    exit 0
    ;;
esac
