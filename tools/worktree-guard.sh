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
#     session tree (e.g. fervent-colden-*), or any other non-dispatch tree.
#     SECONDARY guard: branch must be LANDED — defined as having a MERGED PR AND
#     no OPEN PR (via gh pr list --state merged/open). Correctly handles
#     squash-merged branches whose remote ref persists (the old ls-remote check
#     missed these). Requires gh; soft-degrades to no-op if gh is absent.
#     LOCK HANDLING: locked worktrees only force-removed when locking pid is dead;
#     alive pid or unparseable reason → skip (soft-degrade).
#     BRANCH CLEANUP: after removing a landed worktree, deletes the local branch
#     and the lingering remote branch if it still exists on origin.
#     DEPTH guards: skip the current worktree; skip the root worktree.
#     All four conditions: agent-* path AND landed AND not-current AND not-root.
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
    # is_branch_landed <branch>
    #   Returns 0 (true) iff the branch has a MERGED PR AND no OPEN PR.
    #   Soft-degrade: if gh is missing or network fails → returns 1 (not landed).
    #   A branch with NO PR or an OPEN PR is NEVER considered landed.
    is_branch_landed() {
      local br="$1"
      # Require gh — hard dependency for merged-PR detection.
      if ! command -v gh >/dev/null 2>&1; then
        return 1  # gh absent → soft-degrade: treat as not landed
      fi
      # Count merged PRs for this branch head.
      local merged_count
      merged_count=$(gh pr list --head "$br" --state merged --json number -q 'length' 2>/dev/null) || return 1
      # Network error or empty output → soft-degrade.
      if [ -z "$merged_count" ]; then
        return 1
      fi
      # No merged PR → not landed.
      if [ "$merged_count" -eq 0 ] 2>/dev/null; then
        return 1
      fi
      # Count open PRs — a branch with an open PR is NEVER pruned.
      local open_count
      open_count=$(gh pr list --head "$br" --state open --json number -q 'length' 2>/dev/null) || return 1
      if [ -z "$open_count" ]; then
        return 1
      fi
      if [ "$open_count" -gt 0 ] 2>/dev/null; then
        return 1
      fi
      # merged > 0 AND open == 0 → landed.
      return 0
    }

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

    # Fetch origin so remote state is current for branch-cleanup checks.
    git fetch origin 2>/dev/null || true

    # Soft-degrade if gh is absent — merged-PR detection requires it.
    if ! command -v gh >/dev/null 2>&1; then
      git worktree prune 2>/dev/null || true
      exit 0
    fi

    # Iterate worktrees via porcelain output, parsing worktree + branch lines.
    WORKTREE_PATH=""
    WORKTREE_BRANCH=""
    WORKTREE_LOCKED=""
    WORKTREE_LOCK_REASON=""
    while IFS= read -r line; do
      case "$line" in
        "worktree "*)
          WORKTREE_PATH="${line#worktree }"
          WORKTREE_BRANCH=""
          WORKTREE_LOCKED=""
          WORKTREE_LOCK_REASON=""
          ;;
        "branch refs/heads/"*)
          WORKTREE_BRANCH="${line#branch refs/heads/}"
          ;;
        "locked"*)
          WORKTREE_LOCKED="1"
          WORKTREE_LOCK_REASON="${line#locked}"
          WORKTREE_LOCK_REASON="${WORKTREE_LOCK_REASON# }"
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
                WORKTREE_LOCKED=""
                WORKTREE_LOCK_REASON=""
                continue
                ;;  # not a dispatch tree — skip unconditionally
            esac

            # DEPTH GUARD 1: skip the current worktree.
            if [ "$WORKTREE_PATH" = "$CURRENT_TREE" ]; then
              WORKTREE_PATH=""
              WORKTREE_BRANCH=""
              WORKTREE_LOCKED=""
              WORKTREE_LOCK_REASON=""
              continue
            fi

            # DEPTH GUARD 2: skip the root repo worktree.
            if [ "$WORKTREE_PATH" = "$ROOT_TREE" ]; then
              WORKTREE_PATH=""
              WORKTREE_BRANCH=""
              WORKTREE_LOCKED=""
              WORKTREE_LOCK_REASON=""
              continue
            fi

            # When uncertain (no branch / detached HEAD), leave it.
            if [ -z "$WORKTREE_BRANCH" ]; then
              WORKTREE_PATH=""
              WORKTREE_LOCKED=""
              WORKTREE_LOCK_REASON=""
              continue
            fi

            # SECONDARY GUARD: branch must be landed (merged PR + no open PR).
            # Replaces the old "branch gone from origin" ls-remote check, which
            # missed squash-merged worktrees whose remote branch persists because
            # it is checked out in a sibling worktree (--delete-branch skip).
            # All guards passed: agent-* AND landed AND not-current AND not-root.
            if is_branch_landed "$WORKTREE_BRANCH"; then
              # LOCK HANDLING: if worktree is locked, check if the locking pid is alive.
              # Only override the lock if the pid is confirmed dead; skip (soft-degrade)
              # if the pid is alive or cannot be parsed.
              if [ -n "$WORKTREE_LOCKED" ]; then
                # Try to parse a numeric pid from the lock reason (e.g. "locked by pid 12345").
                LOCK_PID=$(printf '%s' "$WORKTREE_LOCK_REASON" | grep -oE '[0-9]+' | head -1)
                if [ -n "$LOCK_PID" ]; then
                  if kill -0 "$LOCK_PID" 2>/dev/null; then
                    # Pid is alive — skip this worktree (soft-degrade).
                    WORKTREE_PATH=""
                    WORKTREE_BRANCH=""
                    WORKTREE_LOCKED=""
                    WORKTREE_LOCK_REASON=""
                    continue
                  fi
                  # Pid is dead → stale lock; safe to force-remove.
                  git worktree remove -f -f "$WORKTREE_PATH" 2>/dev/null || true
                else
                  # Cannot parse a pid → soft-degrade: skip this worktree.
                  WORKTREE_PATH=""
                  WORKTREE_BRANCH=""
                  WORKTREE_LOCKED=""
                  WORKTREE_LOCK_REASON=""
                  continue
                fi
              else
                # Not locked — standard force-remove (unlock is a no-op but harmless).
                git worktree remove --force "$WORKTREE_PATH" 2>/dev/null || true
              fi

              # BRANCH CLEANUP: delete local branch + lingering remote branch.
              # git branch -D: ignore error if branch is checked out elsewhere.
              git branch -D "$WORKTREE_BRANCH" 2>/dev/null || true
              # Only push --delete if the remote ref still exists.
              if git ls-remote --exit-code origin "$WORKTREE_BRANCH" >/dev/null 2>&1; then
                git push origin --delete "$WORKTREE_BRANCH" 2>/dev/null || true
              fi
            fi
          fi
          WORKTREE_PATH=""
          WORKTREE_BRANCH=""
          WORKTREE_LOCKED=""
          WORKTREE_LOCK_REASON=""
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
