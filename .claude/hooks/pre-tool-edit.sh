#!/bin/bash
# PreToolUse(Edit|MultiEdit|Write) hook — escalate rule-#10 main-agent writes per ADR-0023 D3.
# Reads tool-call JSON on stdin; inspects tool_input.file_path.
# Emits hookSpecificOutput.permissionDecision: "ask" for tracked-file writes from main-agent context.
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

# Tracked-file check; if tracked → escalate.
REL="${FP#"$PWD"/}"
if git ls-files --error-unmatch -- "$REL" >/dev/null 2>&1 || git ls-files --error-unmatch -- "$FP" >/dev/null 2>&1; then
  emit_ask
fi

exit 0
