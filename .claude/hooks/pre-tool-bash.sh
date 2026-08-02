#!/bin/bash
# PreToolUse(Bash) hook — deny-guard for dangerous git ops and incident-backed pipeline bypasses.
# Covers ADR-0023 D4 (push-to-main) and the ADR-0076 D4 deny-guard funnel
# (PRD #1127 criteria 7a-7c, slice #1133): three raw forms below, each with
# a working sanctioned alternative.
# Reads tool-call JSON on stdin; inspects tool_input.command.
# Denies (permissionDecision: "deny"):
#   - `git push` targeting main via ANY refspec form: plain `origin main`,
#     `HEAD:main`/`<src>:main`, `:main` (delete-remote-main), and
#     `refs/heads/main` (bare, or as a colon-form destination) — ADR-0023 D4 +
#     ADR-0076 D4 7c, closing the refspec evasion of the original
#     origin-main-only regex.
#   - raw `gh pr merge` (any flags) — ADR-0076 D4 7a, upgraded from the
#     advisory warn added in PRD #1075 slice #1086. Names `tools/pipe/pr-merge`
#     as the sanctioned wrapper. The wrapper's own internal
#     `subprocess.run(["gh","pr","merge",...])` call is a Python-internal
#     subprocess invisible to this hook — Claude Code's PreToolUse(Bash) hook
#     only ever sees the literal Bash-tool command line
#     (`python tools/pipe/pr-merge <pr>`), which contains no `gh pr merge`
#     substring, so the sanctioned wrapper invocation is never mis-denied.
#   - `tools/promote.sh` invoked from a SUBAGENT context — ADR-0076 D4 7b,
#     reusing the identical `CLAUDE_AGENT_TYPE` env-var discriminator
#     `pre-tool-edit.sh` already uses (~line 71) for its subagent-context
#     skip; the orchestrator's own (main-agent, no CLAUDE_AGENT_TYPE)
#     invocation passes through un-denied.
# Warns (systemMessage, NOT denied):
#   - `git commit ... -m ... WIP` (convention nudge).
# Soft-degrades if `jq` missing → exit 0 (cannot parse; let Claude's built-in classifier handle).
set -uo pipefail

# Resolve main root + LOG_DIR via lib-root.sh (PRD #668 beacon unification).
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
# shellcheck source=lib-root.sh
source "$SCRIPT_DIR/lib-root.sh"

printf '{"hook":"pre-tool-bash","ts":"%s"}\n' "$(date -u -Iseconds 2>/dev/null)" >> "$LOG_DIR/hook-fires.jsonl" 2>/dev/null || true

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

# `git push` targeting main via ANY refspec form (ADR-0076 D4 7c): plain
# `origin main`; `<src>:main` incl. `HEAD:main` and `:main` (delete-remote-main,
# colon immediately followed by `main`); or `refs/heads/main` (bare arg, or as
# a colon-form destination e.g. `HEAD:refs/heads/main`). Covers --force /
# --force-with-lease / any flags between `push` and the refspec.
if echo "$CMD" | grep -qE 'git[[:space:]]+push' \
   && echo "$CMD" | grep -qE '(\borigin[[:space:]]+main\b|:main\b|\brefs/heads/main\b)'; then
  emit_deny 'Direct push to main forbidden per CLAUDE.md rule #4 (all refspec forms denied: origin main, HEAD:main, refs/heads/main, :main); open a PR instead.'
fi

# `git commit -m "... WIP ..."` → warn-only (convention, not danger).
if echo "$CMD" | grep -qE 'git[[:space:]]+commit.*-m.*\bWIP\b'; then
  emit_warn 'WIP commit detected — CLAUDE.md rule #5 discourages WIP messages; prefer Conventional Commits.'
fi

# `tools/promote.sh` invoked from a SUBAGENT context (ADR-0076 D4 7b) → deny.
# Reuses pre-tool-edit.sh's CLAUDE_AGENT_TYPE discriminator exactly: subagent
# contexts set this env var, the main-agent orchestrator does not. Promotion
# is a human-gated orchestrator action (see #880) — implementer.md and
# reviewer.md already prohibit it in prose; this makes the prohibition
# mechanical for subagent-context Bash invocations. Orchestrator-context
# invocations (no CLAUDE_AGENT_TYPE) fall through un-denied.
if echo "$CMD" | grep -qE 'tools/promote\.sh'; then
  if [ -n "${CLAUDE_AGENT_TYPE:-}" ]; then
    emit_deny 'tools/promote.sh may not run from a subagent context — promotion is a human-gated orchestrator action (see #880); only the orchestrator invokes it directly.'
  fi
fi

# Raw `gh pr merge` → DENY (ADR-0076 D4 7a; upgraded from the advisory warn
# added in PRD #1075 slice #1086). The sanctioned tools/pipe/pr-merge wrapper
# appends the atomic pr_merged v3 span a raw call skips, and asserts the
# reviewer APPROVE verdict (ADR-0076 D3) a raw call never checks. The wrapper
# invocation itself (`python tools/pipe/pr-merge <pr>`) contains no `gh pr
# merge` substring at the Bash-command level — its `gh pr merge` subprocess
# call happens INSIDE the Python process, never as a Bash tool call this hook
# observes — so this deny never fires on the sanctioned wrapper.
if echo "$CMD" | grep -qE 'gh[[:space:]]+pr[[:space:]]+merge\b'; then
  emit_deny 'Raw `gh pr merge` denied — bypasses tools/pipe/pr-merge (no v3 pr_merged span, no APPROVE-verdict assertion). Use `python tools/pipe/pr-merge <PR>` instead.'
fi

exit 0
