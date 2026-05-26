#!/bin/bash
# PreToolUse(Edit|MultiEdit|Write) hook — extended per ADR-0028 with spec-gate.
#
# Layered behavior (in order):
#  1. Subagent context skip (CLAUDE_AGENT_TYPE set) — exit 0; subagents ARE the PR pipeline.
#  2. tool-results/ + .claude/projects/ allowlist — exit 0.
#  3. Tracked-file check; non-tracked files → exit 0.
#  4. Spec-gate (ADR-0028 D1+D2): for main-agent edits to tracked files, parse branch and
#     verify an in-flight PRD/slice issue exists. DENY when no matching issue / no matching
#     branch pattern / issue closed. Fall through to rule-#10 ask when issue exists+open.
#     Soft-degrades to ask if `gh` is unavailable OR returns a network error (ADR-0028 D4).
#  5. Rule-#10 escalate-to-ask fallback (preserved from ADR-0023 D3).
#
# Soft-degrades if `jq` is missing → always emit "ask" (escalate, don't silently allow).

set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || true

REASON='Main-agent write to tracked file — CLAUDE.md rule #10 says flow through PR pipeline. Confirm if this is an I3 trivial-lane edit (≤10 LoC, `trivial` label, branch `hotfix/<issue#>-…`); cancel and use /to-prd or /ship otherwise.'

emit_ask() {
  if command -v jq >/dev/null 2>&1; then
    jq -cn --arg r "$REASON" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: $r}}'
  else
    ESC=$(printf '%s' "$REASON" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"%s"}}\n' "$ESC"
  fi
  exit 0
}

# ADR-0028 D2: spec-gate denies tracked-file edits when branch lacks an in-flight PRD/slice issue.
emit_deny() {
  local reason="$1"
  if command -v jq >/dev/null 2>&1; then
    jq -cn --arg r "$reason" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $r}}'
  else
    ESC=$(printf '%s' "$reason" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$ESC"
  fi
  exit 0
}

# Subagent context — allow (no emit). Subagents ARE the PR pipeline per ADR-0023 D3 step 1.
# OQ-1 fallback: if CLAUDE_AGENT_TYPE unreliable on dogfood, comment out this block to always escalate.
if [ -n "${CLAUDE_AGENT_TYPE:-}" ]; then
  exit 0
fi

# Missing jq → cannot parse stdin reliably; escalate (default-conservative per OQ-1 fallback).
if ! command -v jq >/dev/null 2>&1; then
  emit_ask
fi

FP=$(jq -r '.tool_input.file_path // ""' </dev/stdin 2>/dev/null || echo "")
[ -z "$FP" ] && exit 0

# Allowlist: transcripts / tool-results / paths the user explicitly excludes.
case "$FP" in
  */.claude/projects/*|*/tool-results/*|*.claude/projects/*|*tool-results/*) exit 0 ;;
esac

# Tracked-file check; if NOT tracked → exit cleanly (no spec-gate, no ask).
REL="${FP#"$PWD"/}"
if ! git ls-files --error-unmatch -- "$REL" >/dev/null 2>&1 && ! git ls-files --error-unmatch -- "$FP" >/dev/null 2>&1; then
  exit 0
fi

# ADR-0028 D1+D2: spec-gate runs BEFORE rule-#10 ask fallback for tracked-file edits.
# Soft-degrades per D4: if `gh` missing OR `gh issue view` returns a network error, fall through to ask.
if command -v gh >/dev/null 2>&1; then
  BRANCH="${BRANCH:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null)}"
  N=""
  if printf '%s' "$BRANCH" | grep -qE '^(feat|fix|docs|chore|refactor|test|perf|style|build|ci)/[0-9]+-'; then
    N=$(printf '%s' "$BRANCH" | sed -E 's|^[a-z]+/([0-9]+)-.*|\1|')
  elif printf '%s' "$BRANCH" | grep -qE '^hotfix/[0-9]+-'; then
    # ADR-0028 D3 trivial-lane (I3) carveout — hotfix branches require an audit-trail issue
    # but skip the slice/prd label requirement (reviewer enforces `trivial` label at PR time).
    N=$(printf '%s' "$BRANCH" | sed -E 's|^hotfix/([0-9]+)-.*|\1|')
  else
    emit_deny "Branch '$BRANCH' does not match <type>/<issue#>-... or hotfix/<issue#>-... pattern. Run /grill-me + /ship to create a PRD/slice before editing tracked files."
  fi

  # Run gh issue view, capturing stderr to distinguish network errors from missing-issue errors.
  GH_OUT=$(gh issue view "$N" --json state --jq .state 2>/tmp/gh-spec-gate-err.$$ )
  GH_RC=$?
  GH_ERR=$(cat /tmp/gh-spec-gate-err.$$ 2>/dev/null)
  rm -f /tmp/gh-spec-gate-err.$$ 2>/dev/null

  if [ $GH_RC -ne 0 ]; then
    # Distinguish missing-issue (deny) from network error / auth error (soft-degrade to ask).
    if printf '%s' "$GH_ERR" | grep -qiE 'could not resolve|not found|no such issue|graphql.*resolve'; then
      emit_deny "Issue #$N doesn't exist; branch references a stale or invalid issue number. Run /grill-me + /ship for a fresh PRD/slice."
    fi
    # ADR-0028 D4: network / auth / rate-limit errors → soft-degrade to ask (defense-in-depth).
    emit_ask
  fi

  if [ "$GH_OUT" = "CLOSED" ]; then
    emit_deny "Issue #$N is closed; current branch references a closed issue. Run /grill-me + /ship for a fresh PRD/slice."
  fi
  # Issue exists + open — fall through to existing rule-#10 ask.
fi

# Rule-#10 escalate-to-ask fallback (ADR-0023 D3) — preserved for tracked-file edits when
# spec-gate either passed (issue open) or soft-degraded (gh unavailable).
emit_ask
