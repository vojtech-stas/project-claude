#!/bin/bash
# UserPromptSubmit hook — topic-nudge per ADR-0026 D4.
# Reads UserPromptSubmit JSON on stdin; inspects .prompt against .claude/topics.json.
# For each topic with a keyword match (case-insensitive, word-boundary aware),
# emits hookSpecificOutput.additionalContext nudging main to dispatch current-state-reader.
# Soft-degrades if `jq` missing → exit 0 (no nudge; not a blocker; per ADR-0023 D5 pattern).
set -uo pipefail

TOPICS_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/topics.json"

if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

if [ ! -f "$TOPICS_FILE" ]; then
  exit 0
fi

PROMPT=$(jq -r '.prompt // ""' </dev/stdin 2>/dev/null || echo "")
[ -z "$PROMPT" ] && exit 0

# Collect matched topics (one per line) by iterating topic→keywords entries.
# Word-boundary grep on each keyword keeps precision per ADR-0026 OQ-4.
MATCHED=$(jq -r 'to_entries[] | "\(.key)\t\(.value | join("|"))"' "$TOPICS_FILE" 2>/dev/null | \
  while IFS=$'\t' read -r topic keywords; do
    [ -z "$topic" ] && continue
    [ -z "$keywords" ] && continue
    # Build alternation pattern; word-boundary anchors on each side.
    # Some keywords contain spaces/hyphens; use literal grep with -i + -w-ish framing.
    if echo "$PROMPT" | grep -iqE "(^|[^a-zA-Z0-9-])(${keywords})([^a-zA-Z0-9-]|\$)"; then
      echo "$topic"
    fi
  done)

[ -z "$MATCHED" ] && exit 0

# Build one combined nudge listing all detected topics (per ADR-0026 D4 multi-match rule).
TOPIC_LIST=$(echo "$MATCHED" | paste -sd ',' -)
NUDGE="Topic(s) detected in prompt: ${TOPIC_LIST}. Dispatch the current-state-reader subagent (subagent_type: current-state-reader) with the topic string BEFORE answering — once per topic. Do NOT read source ADRs, skill bodies, or subagent bodies inline; the truth-doc surface (docs/current/<topic>.md) is the canonical \"what's true today\" answer per ADR-0026 D1+D3. If a topic has no truth-doc, the reader will return INVALID_INPUT — that signals a backfill gap, not a defect; consider /grill-me on the topic if the gap is blocking work."

jq -cn --arg c "$NUDGE" '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: $c}}'

exit 0
