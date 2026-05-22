#!/usr/bin/env bash
# bootstrap.sh — fresh-clone setup for project-claude
#
# Purpose:
#   Bring a fresh clone of this repo to a usable state in one command.
#   Run this once after `git clone`. Re-running is safe (idempotent).
#
# Scope (per ADR-0008 D6, slice #60):
#   1. Sanity: confirm we're inside a git repo + `gh` is authenticated.
#   2. Create the 6 repo-level labels (skip if they already exist).
#   3. Install local git hooks (`git config core.hooksPath .githooks`).
#   4. Detect the GitHub Project v2 board (manual hint if missing).
#   5. Apply branch protection R1+R2 on `main` (warn-and-proceed if no admin).
#
# Explicit DEFERRALS (NOT done here):
#   - Matt Pocock skills install                    — user-level concern
#   - MCP server configuration                      — user-level concern
#   - CI / GitHub Actions / bot identity            — deferred to PRD-CI
#   - Branch protection R3 (status checks)          — deferred to PRD-CI
#   - Branch protection R4 (non-author review)      — deferred to PRD-CI
#   - `--global` git config changes                 — out of scope
#   - `--check` / dry-run mode                      — YAGNI (ADR-0008 OQ)
#   - GitHub Project v2 board creation              — complex GraphQL; manual
#
# Failure mode:
#   Best-effort. `set -uo pipefail` only — NOT `-e`. Per-step failures
#   warn and continue; the script never aborts on a single-step failure.
#
# See:
#   - decisions/0008-workflow-autolog-bootstrap-and-naming.md (D6)
#   - .githooks/install.sh, .githooks/pre-commit
#   - decisions/branch-protection-config.json (reference shape)

set -uo pipefail

readonly SCRIPT_NAME="bootstrap.sh"
readonly SCRIPT_VERSION="0.1.0 (slice #60)"
readonly TAG="[${SCRIPT_NAME}]"

# Outcome lines accumulated by each step, printed in the final summary.
SUMMARY=()

# ---- helpers --------------------------------------------------------------

log()  { printf '%s %s\n' "$TAG" "$*"; }
warn() { printf '%s WARN: %s\n' "$TAG" "$*" >&2; }
step() { printf '\n%s step %s: %s\n' "$TAG" "$1" "$2"; }
note() { SUMMARY+=("$1"); }

# Resolve <owner>/<repo> from the origin remote. Supports both SSH
# (`git@github.com:owner/repo.git`) and HTTPS (`https://github.com/owner/repo.git`).
# Echoes "owner/repo" on success; non-zero exit on failure.
resolve_origin_slug() {
    local url
    url=$(git remote get-url origin 2>/dev/null) || return 1
    # Strip optional trailing ".git"
    url="${url%.git}"
    # SSH form: git@host:owner/repo
    if [[ "$url" =~ ^git@[^:]+:([^/]+/[^/]+)$ ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}"
        return 0
    fi
    # HTTPS form: https://host/owner/repo  (or http://)
    if [[ "$url" =~ ^https?://[^/]+/([^/]+/[^/]+)$ ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}"
        return 0
    fi
    return 1
}

# ---- step 1: sanity checks ------------------------------------------------

step 1 "sanity checks"

# 1a. We must be inside a git work tree. The script is runnable from any
# subdirectory, but if we aren't in *any* git tree we can't do anything useful.
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || REPO_ROOT=""
if [[ -z "$REPO_ROOT" ]]; then
    warn "not inside a git repository; cannot proceed with most steps."
    note "⚠ sanity: not inside a git repo — aborting"
    # Print summary and exit early; nothing else will work.
    printf '\n%s ---- summary ----\n' "$TAG"
    for line in "${SUMMARY[@]}"; do printf '%s   %s\n' "$TAG" "$line"; done
    exit 1
fi

CWD_ABS=$(pwd -P 2>/dev/null || pwd)
REPO_ROOT_ABS=$(cd "$REPO_ROOT" && pwd -P 2>/dev/null || pwd)
if [[ "$CWD_ABS" != "$REPO_ROOT_ABS" ]]; then
    warn "not at repo root ($REPO_ROOT_ABS); the script will operate against the repo root anyway."
fi

log "$SCRIPT_NAME $SCRIPT_VERSION — repo root: $REPO_ROOT_ABS"

# 1b. Confirm `gh` is installed AND authenticated. Without it, every
# subsequent step that talks to GitHub will fail.
if ! command -v gh >/dev/null 2>&1; then
    warn "'gh' CLI not found on PATH; GitHub-touching steps will be skipped."
    note "⚠ sanity: gh CLI missing — GitHub steps skipped"
    GH_OK=0
elif ! gh auth status >/dev/null 2>&1; then
    warn "'gh auth status' failed; run 'gh auth login' first."
    note "⚠ sanity: gh not authenticated — GitHub steps skipped"
    GH_OK=0
else
    log "gh CLI present and authenticated."
    note "✓ sanity: git repo + gh authenticated"
    GH_OK=1
fi

# Resolve the origin slug once; reused by label + branch-protection steps.
ORIGIN_SLUG=""
if [[ "$GH_OK" -eq 1 ]]; then
    ORIGIN_SLUG=$(resolve_origin_slug) || ORIGIN_SLUG=""
    if [[ -z "$ORIGIN_SLUG" ]]; then
        warn "could not parse <owner>/<repo> from origin remote URL; some steps may be skipped."
    else
        log "origin slug resolved to: $ORIGIN_SLUG"
    fi
fi

# ---- step 2: create the 6 repo-level labels -------------------------------

step 2 "create repo labels (idempotent)"

# Label spec — keep aligned with CLAUDE.md "Hierarchy — PRD → Slice → PR".
# Format: "<name>|<color-hex>|<description>"
LABELS=(
    "prd|a2eeef|Product Requirements Document"
    "slice|0075ca|INVEST-shaped vertical slice of a PRD"
    "backlog|cccccc|Forward-looking work queue item; not yet a PRD"
    "captured|8b949e|Graveyard of backlog-critic rejects per ADR-0008 D1; lazy human review"
    "trivial|fbca04|≤10 LoC runtime; I3 trivial-lane PR; reviewer fast-paths"
    "needs-human|d93f0b|Round-3 BLOCK escalation per I5"
)

create_label() {
    local name="$1" color="$2" desc="$3"
    # `gh label list` output begins with the label name in column 1, tab-separated.
    # We grep with a tab anchor to avoid prefix-collisions like `prd` vs `prd-foo`.
    if gh label list --repo "$ORIGIN_SLUG" --limit 200 2>/dev/null | grep -q "^${name}"$'\t'; then
        log "label '$name' already exists; skipping."
        return 0
    fi
    if gh label create "$name" --color "$color" --description "$desc" --repo "$ORIGIN_SLUG" >/dev/null 2>&1; then
        log "label '$name' created."
        return 0
    fi
    warn "failed to create label '$name'."
    return 1
}

if [[ "$GH_OK" -eq 1 && -n "$ORIGIN_SLUG" ]]; then
    created=0
    skipped=0
    failed=0
    for spec in "${LABELS[@]}"; do
        IFS='|' read -r name color desc <<<"$spec"
        # We re-grep per-label to keep idempotency check tight; the per-call
        # cost (one `gh label list` per label) is acceptable for 6 labels.
        before=$(gh label list --repo "$ORIGIN_SLUG" --limit 200 2>/dev/null | grep -c "^${name}"$'\t' || true)
        if create_label "$name" "$color" "$desc"; then
            if [[ "$before" -eq 0 ]]; then created=$((created+1)); else skipped=$((skipped+1)); fi
        else
            failed=$((failed+1))
        fi
    done
    note "✓ labels: ${created} created, ${skipped} already existed, ${failed} failed"
else
    warn "skipping label creation (gh not ready or origin slug unresolved)."
    note "⚠ labels: skipped (gh not ready)"
fi

# ---- step 3: install git hooks --------------------------------------------

step 3 "install git hooks (core.hooksPath = .githooks)"

# Setting core.hooksPath is itself idempotent — setting it to the same value
# is a no-op. We compare before/after to report an honest "already done" vs
# "newly set" outcome in the summary.
HOOKS_BEFORE=$(git -C "$REPO_ROOT" config --local --get core.hooksPath 2>/dev/null || echo "")
if git -C "$REPO_ROOT" config --local core.hooksPath .githooks 2>/dev/null; then
    if [[ "$HOOKS_BEFORE" == ".githooks" ]]; then
        log "core.hooksPath was already '.githooks'; no change."
        note "✓ git hooks: already configured"
    else
        log "core.hooksPath set to '.githooks' (was: '${HOOKS_BEFORE:-<unset>}')."
        note "✓ git hooks: configured (.githooks)"
    fi
else
    warn "failed to set core.hooksPath."
    note "⚠ git hooks: failed to configure"
fi

# Best-effort: ensure the hook scripts are executable. On Windows filesystems
# the bit is ignored, but chmod still succeeds; on POSIX it actually matters.
# We silently skip any file that doesn't exist (e.g., partial clone).
for f in "$REPO_ROOT/.githooks/pre-commit" "$REPO_ROOT/.githooks/install.sh"; do
    if [[ -f "$f" ]]; then
        chmod +x "$f" 2>/dev/null || warn "could not chmod +x '$f' (likely Windows filesystem; git index bit still applies)."
    fi
done

# Same idempotent chmod for Claude Code hook scripts under .claude/hooks/
# (per ADR-0023 D7). Glob expands to nothing if the directory is missing on a
# partial clone; the `|| true` keeps the script best-effort.
[ -d "$REPO_ROOT/.claude/hooks" ] && chmod +x "$REPO_ROOT"/.claude/hooks/*.sh 2>/dev/null || true

# ---- step 4: project board v2 (detect only; manual create if missing) -----

step 4 "GitHub Project v2 board (detect only)"

# Honest scope: creating a v2 project board requires GraphQL mutations
# (projectV2Create, then adding fields, then creating single-select options
# for each column). That's complex enough to deserve its own slice. For now
# we only detect existence and print a manual-setup hint if missing.
#
# Owner is derived from origin slug; we list projects owned by that user/org
# and treat "any project exists" as "good enough" — the columns Backlog /
# Captured / Todo / In Progress / Done are assumed configured per ADR-0008 D6.
if [[ "$GH_OK" -eq 1 && -n "$ORIGIN_SLUG" ]]; then
    OWNER="${ORIGIN_SLUG%%/*}"
    # `gh project list` requires the `project` scope on the token. If the
    # token lacks it, the command fails — that's a warn, not an error.
    if gh project list --owner "$OWNER" --limit 50 >/dev/null 2>&1; then
        proj_count=$(gh project list --owner "$OWNER" --limit 50 --format json 2>/dev/null \
            | grep -o '"number"' | wc -l | tr -d ' ')
        if [[ "$proj_count" -gt 0 ]]; then
            log "found $proj_count project(s) owned by '$OWNER'."
            log "✓ project board exists; columns assumed configured per ADR-0008 D6."
            note "✓ project board: detected ($proj_count owned by $OWNER)"
        else
            warn "no project boards found for owner '$OWNER'."
            warn "manual setup required — create a v2 project with columns:"
            warn "    Backlog, Captured, Todo, In Progress, Done"
            warn "see ADR-0008 D6. Suggested command:"
            warn "    gh project create --owner $OWNER --title 'project-claude pipeline'"
            note "⚠ project board: none found — manual setup required"
        fi
    else
        warn "'gh project list' failed (token may lack 'project' scope or org permission)."
        warn "skipping project board check. To grant the scope: gh auth refresh -s project,read:project"
        note "⚠ project board: detection skipped (missing 'project' scope)"
    fi
else
    warn "skipping project board check (gh not ready)."
    note "⚠ project board: skipped (gh not ready)"
fi

# ---- step 5: branch protection R1 + R2 on main ----------------------------

step 5 "branch protection R1+R2 on main"

# R1 = require PR (required_pull_request_reviews block present, count=0).
# R2 = no force-push, no deletion (allow_force_pushes=false, allow_deletions=false).
# R3 / R4 are intentionally OMITTED here — they depend on CI infrastructure
# (status checks, code owners) and ship in PRD-CI.
#
# This call requires admin permission on the repo. Fork contributors and
# non-admin collaborators will get 403 — that's the canonical warn-and-proceed
# case. We discard stderr so the contributor isn't scared by a raw API error;
# the summary line tells them what happened.
BP_BODY='{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}'

if [[ "$GH_OK" -eq 1 && -n "$ORIGIN_SLUG" ]]; then
    if printf '%s' "$BP_BODY" \
        | gh api -X PUT "/repos/${ORIGIN_SLUG}/branches/main/protection" --input - >/dev/null 2>&1; then
        log "branch protection applied to 'main' (R1+R2)."
        note "✓ branch protection: R1+R2 applied to main"
    else
        warn "branch protection requires admin permission; skipping."
        warn "if you're a maintainer, retry with a token that has 'repo' admin scope."
        note "⚠ branch protection: skipped (no admin permission)"
    fi
else
    warn "skipping branch protection (gh not ready or origin slug unresolved)."
    note "⚠ branch protection: skipped (gh not ready)"
fi

# ---- step 6: yt-dlp dep check (warn-only) ---------------------------------

step 6 "yt-dlp dep check (warn-only)"

# yt-dlp is required by the /distill-video skill (per ADR-0019 D3) to fetch
# YouTube transcripts into docs/best-practices/transcripts/. We do NOT
# auto-install it — cross-platform package-manager complexity (winget / brew /
# pip / apt) is a rabbit-hole. Per ADR-0019 D3 + Alt-H rejection: warn-only.
if command -v yt-dlp >/dev/null 2>&1; then
    log "yt-dlp present: $(yt-dlp --version 2>/dev/null | head -1)"
    note "✓ yt-dlp: present"
else
    warn "yt-dlp not on PATH. Required by /distill-video skill (ADR-0019 D3)."
    warn "  Install: pip install yt-dlp  (or: winget install yt-dlp.yt-dlp on Windows; brew install yt-dlp on macOS)"
    note "⚠ yt-dlp: missing (install for /distill-video; otherwise harmless)"
fi

# ---- end-of-run summary ---------------------------------------------------

printf '\n%s ---- summary ----\n' "$TAG"
for line in "${SUMMARY[@]}"; do
    printf '%s   %s\n' "$TAG" "$line"
done
printf '%s done. re-run any time — every step is idempotent.\n' "$TAG"
