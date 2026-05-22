#!/bin/bash
# SessionStart hook — inject live workflow state per ADR-0023 D2.
# Mitigates recurring stale-worktree false-alarm (#173). Reads SessionStart JSON on stdin.
# Emits hookSpecificOutput.additionalContext on stdout, capped 50 lines / 4KB.
# Soft-degrades if `jq`, `gh`, or `git fetch` are unavailable (omit sections; still emit branch + log).
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || true

BR=$(git symbolic-ref --short HEAD 2>/dev/null || echo "(detached)")
DIV="(fetch failed)"
git fetch origin main 2>/dev/null && DIV=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "?")
LOG=$(git log --oneline -5 2>/dev/null || echo "(no log)")

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

CTX=$(printf "Branch: %s | divergence vs origin/main: %s commit(s) behind\n\nRecent commits:\n%s\n\nOpen slices: %s\nOpen PRs: %s\nOpen captured: %s\n" \
  "$BR" "$DIV" "$LOG" "$SL" "$PR" "$CAP" | head -c 4096 | head -n 50)

if [ "$JQ_OK" -eq 1 ]; then
  jq -cn --arg ctx "$CTX" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
else
  ESC=$(printf '%s' "$CTX" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | awk 'BEGIN{ORS="\\n"}{print}')
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$ESC"
fi
