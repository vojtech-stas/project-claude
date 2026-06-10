#!/bin/bash
# SessionStart hook — inject live workflow state per ADR-0023 D2.
# Mitigates recurring stale-worktree false-alarm (#173). Reads SessionStart JSON on stdin.
# Emits hookSpecificOutput.additionalContext on stdout, capped 50 lines / 4KB.
# Soft-degrades if `jq`, `gh`, or `git fetch` are unavailable (omit sections; still emit branch + log).
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || true

# Resolve main root + LOG_DIR via lib-root.sh (PRD #668 beacon unification).
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
# shellcheck source=lib-root.sh
source "$SCRIPT_DIR/lib-root.sh"

# Python3 in-hook self-test: beacon its result (ok/error) so the interpreter
# liveness check is explicit and observable (absence let the jq ENOEXEC hide).
_PY3_STATUS="ok"
python3 -c "import json,sys" 2>/dev/null || _PY3_STATUS="error"
printf '{"hook":"session-start","status":"python3_selftest","result":"%s","ts":"%s"}\n' \
  "$_PY3_STATUS" "$(date -Iseconds 2>/dev/null)" \
  >> "$LOG_DIR/hook-fires.jsonl" 2>/dev/null || true

printf '{"hook":"session-start","ts":"%s"}\n' "$(date -Iseconds 2>/dev/null)" >> "$LOG_DIR/hook-fires.jsonl" 2>/dev/null || true

BR=$(git symbolic-ref --short HEAD 2>/dev/null || echo "(detached)")
DIV="(fetch failed)"
git fetch origin main 2>/dev/null && DIV=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "?")
LOG=$(git log --oneline -5 2>/dev/null || echo "(no log)")

HOOKS_WARN=""
if command -v git >/dev/null 2>&1; then
  HOOKS=$(git config --get core.hooksPath 2>/dev/null || echo "__unset__")
  if [ "$HOOKS" != ".githooks" ]; then
    HOOKS_WARN=$(printf "\n*** WARNING: git core.hooksPath is not '.githooks' (got: %s). Commit-subject length cap and other git hooks are NOT active. Fix: run ./.githooks/install.sh ***\n" "$HOOKS")
  fi
fi

JQ_OK=0; GH_OK=0
command -v jq >/dev/null 2>&1 && JQ_OK=1
[ "$JQ_OK" -eq 1 ] && command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1 && GH_OK=1

q() { gh issue list --label "$1" --state open --json number,title --limit 3 2>/dev/null \
      | jq -r 'if length==0 then "0 open" else "\(length)+ open; recent: \([.[] | "#\(.number) \(.title)"] | join(" | "))" end' 2>/dev/null || echo "(query failed)"; }
SL="(gh/jq unavailable)"; PR="(gh/jq unavailable)"; CAP="(gh/jq unavailable)"
if [ "$GH_OK" -eq 1 ]; then
  SL=$(q slice); CAP=$(q captured)
  PR=$(gh pr list --state open --json number,title --limit 3 2>/dev/null \
       | jq -r 'if length==0 then "0 open" else "\(length)+ open; recent: \([.[] | "#\(.number) \(.title)"] | join(" | "))" end' 2>/dev/null || echo "(query failed)")
fi

# ADR-0030 D4: warn if jq is missing — PreToolUse Edit/Write hook degrades to
# rule-#10 ask on every edit when jq is unavailable (real user-pain per #222).
# Surfacing the warning at session start beats discovering it after 30 prompts.
JQ_WARN=""
if [ "$JQ_OK" -ne 1 ]; then
  JQ_WARN=$(printf "\nWARNING: jq is missing on this system. PreToolUse Edit/Write hook may prompt on every edit (rule #10 ask fallback). Install via bootstrap.sh or winget install jqlang.jq (Windows) / brew install jq (macOS) / apt-get install jq (Linux).\n")
fi

CTX=$(printf "Branch: %s | divergence vs origin/main: %s commit(s) behind\n\nRecent commits:\n%s\n\nOpen slices: %s\nOpen PRs: %s\nOpen captured: %s%s%s\n" \
  "$BR" "$DIV" "$LOG" "$SL" "$PR" "$CAP" "$HOOKS_WARN" "$JQ_WARN" | head -c 4096 | head -n 50)

if [ "$JQ_OK" -eq 1 ]; then
  jq -cn --arg ctx "$CTX" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
else
  ESC=$(printf '%s' "$CTX" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | awk 'BEGIN{ORS="\\n"}{print}')
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$ESC"
fi
