#!/bin/bash
# UserPromptSubmit hook — nudge feature-request prompts toward /grill-me per ADR-0023 D5.
# Also logs skill_invoke events when the user types a /command (ADR-0015/0016).
# Reads UserPromptSubmit JSON on stdin; inspects .prompt and .session_id.
# Emits hookSpecificOutput.additionalContext (non-blocking nudge) if pattern matches.
# Soft-degrades if `jq` missing → exit 0 (no nudge; not a blocker).
# CRITICAL: stdin is captured ONCE at the top; never re-read below.
#
# skill_invoke routing decision (PRD #668 slice #670 open question):
# This hook receives a UserPromptSubmit payload (.prompt, .session_id) — NOT a
# PreToolUse(Skill) payload (.tool_input.skill).  log-tool-event.sh's skill_invoke
# extraction expects the PreToolUse schema; piping a UserPromptSubmit payload would
# produce an event with an empty skill field.  Keeping the emission on log-event.sh
# (which accepts a pre-formatted JSON object) avoids that schema mismatch while still
# producing a correct skill_invoke event.  log-event.sh remains for this use-case
# pending a UserPromptSubmit-aware extraction path in log-tool-event.sh (PRD 5+).
set -uo pipefail

# Resolve main root + LOG_DIR via lib-root.sh (PRD #668 beacon unification).
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
# shellcheck source=lib-root.sh
source "$SCRIPT_DIR/lib-root.sh"

printf '{"hook":"user-prompt-submit","ts":"%s"}\n' "$(date -u -Iseconds 2>/dev/null)" >> "$LOG_DIR/hook-fires.jsonl" 2>/dev/null || true

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
# PRD #876: routes through log-tool-event.sh (log-event.sh deleted).
FIRST_TOKEN=$(echo "$PROMPT" | sed 's/^[[:space:]]*//' | awk '{print $1}')
if [ -n "$FIRST_TOKEN" ] && [ "${FIRST_TOKEN:0:1}" = "/" ]; then
  SKILL_CMD="${FIRST_TOKEN:1}"  # strip leading /
  if [ -n "$SKILL_CMD" ]; then
    # Synthesise a minimal payload that log-tool-event.sh skill_invoke branch can parse.
    _SKILL_PAYLOAD=$(python3 -c "
import json, sys
sid = sys.argv[1]; sk = sys.argv[2]
print(json.dumps({'session_id': sid, 'tool_input': {'skill': sk},
                  'hook_event_name': 'PreToolUse', 'tool_name': 'Skill'}))" \
      "$SID" "$SKILL_CMD" 2>/dev/null || echo "")
    if [ -n "$_SKILL_PAYLOAD" ]; then
      _LTE_DIR="${CLAUDE_PROJECT_DIR:-$(dirname "$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)")}"
      printf '%s' "$_SKILL_PAYLOAD" | bash "$_LTE_DIR/.claude/hooks/log-tool-event.sh" skill_invoke 2>/dev/null || true
    fi
  fi
fi

# --- User-prompt logging (PRD #876 consolidation) ---
# Replaces the standalone settings.json UserPromptSubmit log-tool-event.sh entry.
_LTE_DIR="${CLAUDE_PROJECT_DIR:-$(dirname "$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)")}"
printf '%s' "$STDIN" | bash "$_LTE_DIR/.claude/hooks/log-tool-event.sh" user_prompt 2>/dev/null || true

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
