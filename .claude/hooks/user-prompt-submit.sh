#!/bin/bash
# UserPromptSubmit hook — nudge feature-request prompts toward /grill-me per ADR-0023 D5.
# Reads UserPromptSubmit JSON on stdin; inspects .prompt.
# Emits hookSpecificOutput.additionalContext (non-blocking nudge) if pattern matches.
# Soft-degrades if `jq` missing → exit 0 (no nudge; not a blocker).
set -uo pipefail

NUDGE='User prompt matches feature-request pattern. If the design isn'\''t settled yet, consider /grill-me before /ship.'

if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

PROMPT=$(jq -r '.prompt // ""' </dev/stdin 2>/dev/null || echo "")
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
