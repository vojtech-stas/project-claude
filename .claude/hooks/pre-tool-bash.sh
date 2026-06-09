#!/bin/bash
# PreToolUse(Bash) hook — block dangerous git ops per ADR-0023 D4.
# Reads tool-call JSON on stdin; inspects tool_input.command.
# Patterns:
#   - `git push ... origin main` (any flavor incl. --force/--force-with-lease) → permissionDecision: "deny"
#   - `git commit ... -m ... WIP` → systemMessage warn-only (NOT deny)
# Soft-degrades if `jq` missing → exit 0 (cannot parse; let Claude's built-in classifier handle).
set -uo pipefail
printf '{"hook":"pre-tool-bash","ts":"%s"}\n' "$(date -Iseconds 2>/dev/null)" >> "${CLAUDE_PROJECT_DIR:-$PWD}/.claude/logs/hook-fires.jsonl" 2>/dev/null || true

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

emit_warn() {
  local msg="$1"
  if command -v jq >/dev/null 2>&1; then
    jq -cn --arg m "$msg" '{systemMessage: $m}'
  else
    ESC=$(printf '%s' "$msg" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')
    printf '{"systemMessage":"%s"}\n' "$ESC"
  fi
  exit 0
}

if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

CMD=$(jq -r '.tool_input.command // ""' </dev/stdin 2>/dev/null || echo "")
[ -z "$CMD" ] && exit 0

# `git push` targeting origin main (any flavor; covers --force, --force-with-lease, plain push).
if echo "$CMD" | grep -qE 'git[[:space:]]+push.*\borigin[[:space:]]+main\b'; then
  emit_deny 'Direct push to main forbidden per CLAUDE.md rule #4; open a PR instead.'
fi

# `git commit -m "... WIP ..."` → warn-only (convention, not danger).
if echo "$CMD" | grep -qE 'git[[:space:]]+commit.*-m.*\bWIP\b'; then
  emit_warn 'WIP commit detected — CLAUDE.md rule #5 discourages WIP messages; prefer Conventional Commits.'
fi

exit 0
