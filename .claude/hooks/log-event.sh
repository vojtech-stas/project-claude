#!/bin/bash
# log-event.sh — canonical event-log appender (ADR-0016 / PRD #467 / slice #468).
#
# CONTRACT: reads one event JSON line on stdin; resolves the MAIN repo's
# .claude/logs/workflow-events.jsonl and appends the line there.
#
# HOOKS AUDIT RATIONALE (7 hooks, none redundant):
#   agent_start   PreToolUse·Agent  — fires BEFORE subagent is invoked; captures
#                                     invocation intent + ts for duration-start.
#   agent_complete PostToolUse·Agent — fires AFTER subagent returns; captures
#                                      output + ts for duration-end (span pairing).
#                                      Both are REQUIRED to measure subagent durations.
#   bash_complete  PostToolUse·Bash — fires AFTER the command ran (result available).
#   subagent_edit  PostToolUse·Edit — fires AFTER an edit to a .claude/agents/ file;
#                                     nudges /audit-subagents (writes subagent-edits.log,
#                                     NOT workflow-events.jsonl). Routed via this script
#                                     with LOGFILE override.
#   skill_invoke   PreToolUse·Skill — fires at skill invocation; also detected on
#                                     UserPromptSubmit for typed /commands. Pre is
#                                     correct (the invocation event, not the result).
#                                     NOTE: Skill tool matcher empirically VERIFIED
#                                     2026-06-05 (#430) — skill_invoke events logged for
#                                     ship/build/grill-me/to-prd/to-issues/qa-plan/qa-review.
#   grill_qa       PostToolUse·AskUserQuestion — fires AFTER user answers; captures Q+A.
#                                     NOTE: AskUserQuestion matcher unverified (#402)
#                                     but harmless.
#   session_stop   Stop             — fires at session end; records ts for session-length.
#
# CANONICAL RESOLUTION (per PRD #467):
#   git rev-parse --path-format=absolute --git-common-dir returns <root>/.git for both
#   the main repo AND any linked worktree, so dirname → <root> in all cases.
#
# SOFT-DEGRADE: if git resolution fails, write to $CLAUDE_PROJECT_DIR (worktree).
#   Never exit non-zero. Never lose the event. Never hang.
#
# LOGFILE env var: if set, overrides the target filename within .claude/logs/
#   (used by the subagent-edit nudge which writes subagent-edits.log instead).
#
# Usage (inline loggers in settings.json / user-prompt-submit.sh):
#   jq -cn --arg ... '{...}' | bash "${CLAUDE_PROJECT_DIR}/.claude/hooks/log-event.sh"
#   LOGFILE=subagent-edits.log; echo "..." | bash "...log-event.sh"

LINE=$(cat)
[ -z "$LINE" ] && exit 0

# Extract session_id from the incoming JSON payload (soft-degrade: empty if jq
# missing or field absent).  Mirrors user-prompt-submit.sh's SID extraction.
SID=$(echo "$LINE" | jq -r '.session_id // ""' 2>/dev/null || echo "")

# Stamp session_id into the event object if jq is available and the field is
# absent or empty — purely additive, existing callers that already include it
# are unaffected (jq merges the value, keeping the caller's value if non-empty).
if command -v jq >/dev/null 2>&1 && [ -n "$SID" ]; then
  STAMPED=$(echo "$LINE" | jq -c --arg sid "$SID" '. + {session_id: $sid}' 2>/dev/null)
  [ -n "$STAMPED" ] && LINE="$STAMPED"
fi

# Resolve repo root + LOG_DIR via shared lib (replaces the inlined git-common-dir block).
# shellcheck source=lib-root.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/lib-root.sh"

# Honor WORKFLOW_LOG_DIR sandbox override (used by tests / worktree isolation).
if [ -n "${WORKFLOW_LOG_DIR:-}" ]; then
  LOG_DIR="$WORKFLOW_LOG_DIR"
  mkdir -p "$LOG_DIR" 2>/dev/null || true
fi

printf '{"hook":"log-event","ts":"%s"}\n' "$(date -u -Iseconds 2>/dev/null)" >> "$LOG_DIR/hook-fires.jsonl" 2>/dev/null || true

TARGET_FILE="${LOGFILE:-workflow-events.jsonl}"
printf '%s\n' "$LINE" >> "$LOG_DIR/$TARGET_FILE" 2>/dev/null || true
exit 0
