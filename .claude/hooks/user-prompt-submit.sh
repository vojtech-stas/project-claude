#!/bin/bash
# UserPromptSubmit hook — nudge feature-request prompts toward /grill-me per ADR-0023 D5.
# Also logs skill_invoke events when the user types a /command (ADR-0015/0016).
# Reads UserPromptSubmit JSON on stdin; inspects .prompt and .session_id.
# Emits hookSpecificOutput.additionalContext (non-blocking nudge) if pattern matches.
# Soft-degrades if `jq` missing → exit 0 (no nudge; not a blocker).
# CRITICAL: stdin is captured ONCE at the top; never re-read below.
set -uo pipefail
printf '{"hook":"user-prompt-submit","ts":"%s"}\n' "$(date -Iseconds 2>/dev/null)" >> "${CLAUDE_PROJECT_DIR:-$PWD}/.claude/logs/hook-fires.jsonl" 2>/dev/null || true

NUDGE='User prompt matches feature-request pattern. If the design isn'\''t settled yet, consider /grill-me before /ship.'

if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

# Capture stdin exactly once — both branches below reuse $STDIN.
STDIN=$(cat)

PROMPT=$(echo "$STDIN" | jq -r '.prompt // ""' 2>/dev/null || echo "")
SID=$(echo "$STDIN" | jq -r '.session_id // ""' 2>/dev/null || echo "")

# --- Skill-invoke logging (ADR-0015/0016): detect leading /command ---
# Extract the first non-space token; if it starts with /, capture the command word.
# Soft-degrade: empty prompt, no leading /, empty command word → log nothing, exit 0.
FIRST_TOKEN=$(echo "$PROMPT" | sed 's/^[[:space:]]*//' | awk '{print $1}')
if [ -n "$FIRST_TOKEN" ] && [ "${FIRST_TOKEN:0:1}" = "/" ]; then
  SKILL_CMD="${FIRST_TOKEN:1}"  # strip leading /
  if [ -n "$SKILL_CMD" ]; then
    jq -cn \
      --arg ts "$(date -Iseconds)" \
      --arg sid "$SID" \
      --arg sk "$SKILL_CMD" \
      '{ts: $ts, session_id: $sid, event: "skill_invoke", skill: $sk, source: "user_typed"}' \
      2>/dev/null | bash "${CLAUDE_PROJECT_DIR}/.claude/hooks/log-event.sh" 2>/dev/null || true
  fi
fi

[ -z "$PROMPT" ] && exit 0

# Skip nudge if user already invoked a pipeline command or used the trivial-lane.
if echo "$PROMPT" | grep -qE '/grill-me|/ship|\btrivial\b|\bhotfix\b'; then
  exit 0
fi

# Feature-request trigger patterns per ADR-0023 D5.
if echo "$PROMPT" | grep -qiE '(I want to (build|add|implement))|(we should add)|(let'\''s add)'; then
  jq -cn --arg c "$NUDGE" '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: $c}}'
fi

exit 0
