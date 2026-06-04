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
#     Removes landed dispatch worktrees to prevent unbounded accumulation.
#     SAFETY: only removes worktrees whose path basename starts with "agent-"
#     (the harness dispatch-tree prefix per ADR-0036). This is the PRIMARY safety
#     boundary — it makes it IMPOSSIBLE to remove the root repo, an orchestrator
#     session tree (e.g. fervent-colden-*), or any other non-dispatch tree, even
#     if their branch is absent from origin.
#     SECONDARY guard: branch must be gone from origin (landed/merged).
#     DEPTH guards: skip the current worktree; skip the root worktree.
#     All four conditions must hold: agent-* path AND landed AND not-current AND not-root.
#     SOFT-DEGRADE: skips individual trees on any error; never aborts the whole run.
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
    # Resolve the current worktree path (to implement skip-current guard).
    CURRENT_TREE=$(git rev-parse --show-toplevel 2>/dev/null) || CURRENT_TREE=""

    # Resolve the root repo (same pattern as root-sync above).
    ROOT="${CLAUDE_PROJECT_DIR:-.}"
    COMMON=$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
    if [ -n "$COMMON" ]; then
      ROOT_TREE=$(dirname "$COMMON")
    else
      ROOT_TREE="$ROOT"
    fi

    # Fetch origin so ls-remote reflects the latest remote state.
    git fetch origin 2>/dev/null || true

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
            # PRIMARY SAFETY GUARD: only consider trees whose basename starts with "agent-".
            # This makes it IMPOSSIBLE to remove the root repo, any orchestrator session
            # tree (e.g. fervent-colden-*), or any other non-dispatch tree, regardless of
            # whether their branch is present on origin.
            BASENAME=$(basename "$WORKTREE_PATH")
            case "$BASENAME" in
              agent-*) ;;  # dispatch tree — continue to remaining checks
              *)
                WORKTREE_PATH=""
                WORKTREE_BRANCH=""
                continue
                ;;  # not a dispatch tree — skip unconditionally
            esac

            # DEPTH GUARD 1: skip the current worktree.
            if [ "$WORKTREE_PATH" = "$CURRENT_TREE" ]; then
              WORKTREE_PATH=""
              WORKTREE_BRANCH=""
              continue
            fi

            # DEPTH GUARD 2: skip the root repo worktree.
            if [ "$WORKTREE_PATH" = "$ROOT_TREE" ]; then
              WORKTREE_PATH=""
              WORKTREE_BRANCH=""
              continue
            fi

            # When uncertain (no branch / detached HEAD), leave it.
            if [ -z "$WORKTREE_BRANCH" ]; then
              WORKTREE_PATH=""
              continue
            fi

            # SECONDARY GUARD: branch must be landed (gone from origin).
            # ls-remote exits non-zero when the ref is absent → landed.
            # All guards passed: agent-* AND landed AND not-current AND not-root.
            if ! git ls-remote --exit-code origin "$WORKTREE_BRANCH" >/dev/null 2>&1; then
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
