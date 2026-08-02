#!/bin/bash
# PreToolUse(Bash) hook — deny-guard for dangerous git ops and incident-backed pipeline bypasses.
# Covers ADR-0023 D4 (push-to-main) and the ADR-0076 D4 deny-guard funnel
# (PRD #1127 criteria 7a-7c, slice #1133): three raw forms below, each with
# a working sanctioned alternative.
# Reads tool-call JSON on stdin; inspects tool_input.command.
#
# INVOCATION-ANCHORED, NOT SUBSTRING (reviewer round-1 BLOCK on PR #1141,
# fixed here): every check below classifies the command via a python3 clause
# tokenizer (`classify()`, embedded below) rather than a whole-string grep. The raw
# command is split into "clauses" on unquoted shell separators (`;`, `&`,
# `&&`, `|`, `||`, newline) using `shlex.shlex(..., posix=True,
# punctuation_chars=True)` (quotes are honored — a quoted phrase collapses
# into ONE token, so it can never masquerade as an adjacent command word).
# Each clause is checked independently by its OWN first token(s) (skipping
# leading `VAR=val` env-prefixes) — a mention of a dangerous phrase inside an
# unrelated command's argument (a commit message, an echo, a grep pattern)
# never matches, and a dangerous clause in a compound command is never
# rescued by an unrelated mention in another clause. Full parsing of
# command-substitution subshells (`$(...)`, backticks) is intentionally out
# of scope (ADR-0076 D4 rabbit-hole discipline — see PR body); each clause is
# examined independently, so under-splitting only ever makes detection MORE
# conservative, never less.
# Denies (permissionDecision: "deny"):
#   - `git push` targeting main via ANY refspec form: plain `origin main`,
#     `HEAD:main`/`<src>:main`, `:main` (delete-remote-main), and
#     `refs/heads/main` (bare, or as a colon-form destination) — ADR-0023 D4 +
#     ADR-0076 D4 7c, closing the refspec evasion of the original
#     origin-main-only regex. Refspec matching is scoped to tokens WITHIN
#     the same `git push` clause only.
#   - raw `gh pr merge` (any flags, as the actual invocation — clause's first
#     three tokens literally `gh`, `pr`, `merge`) — ADR-0076 D4 7a, upgraded
#     from the advisory warn added in PRD #1075 slice #1086. Names
#     `tools/pipe/pr-merge` as the sanctioned wrapper. The wrapper's own
#     internal `subprocess.run(["gh","pr","merge",...])` call is a
#     Python-internal subprocess invisible to this hook — Claude Code's
#     PreToolUse(Bash) hook only ever sees the literal Bash-tool command line
#     (`python tools/pipe/pr-merge <pr>`), whose first clause-token is
#     `python`, never `gh`, so the sanctioned wrapper invocation is never
#     mis-denied.
#   - `tools/promote.sh` invoked (as the clause's actual command, not a
#     mention) from a SUBAGENT context — ADR-0076 D4 7b, reusing the
#     identical `CLAUDE_AGENT_TYPE` env-var discriminator `pre-tool-edit.sh`
#     already uses (~line 71) for its subagent-context skip; the
#     orchestrator's own (main-agent, no CLAUDE_AGENT_TYPE) invocation passes
#     through un-denied.
# Warns (systemMessage, NOT denied):
#   - `git commit ... -m ... WIP` (convention nudge; same clause-anchoring
#     applied per rule #19 class-sweep).
# Soft-degrades if `jq` OR `python3` missing → ERROR beacon + exit 0 (cannot
# classify; let Claude's built-in classifier handle. jq itself is still
# required for the earlier `tool_input.command` extraction and for the
# emit_deny/emit_warn JSON builders).
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

emit_error_beacon() {
  local reason="$1"
  printf '{"hook":"pre-tool-bash","status":"ERROR","ts":"%s","reason":"%s"}\n' \
    "$(date -u -Iseconds 2>/dev/null)" "$reason" \
    >> "$LOG_DIR/hook-fires.jsonl" 2>/dev/null || true
}

if ! command -v python3 >/dev/null 2>&1; then
  emit_error_beacon 'python3 unavailable -- clause-anchored deny-guard classification skipped, fail-open'
  exit 0
fi

# Clause-anchored classification (fixes reviewer round-1 BLOCK on PR #1141:
# F1 substring-vs-invocation for 7a, F2 clause-decoupling for 7c, + rule #19
# sweep of the same weakness in 7b and the WIP warn). Passed via env var
# (mirrors pre-tool-edit.sh's `_PTE_STDIN` pattern) rather than heredoc
# interpolation, so quotes/backticks/`$` in CMD are never re-interpreted by
# bash.
_PTB_JSON=$(export _PTB_CMD="$CMD"; python3 - <<'PYEOF' 2>/dev/null
import json, os, re, shlex

BOUNDARY_TOKENS = {";", "&", "&&", "|", "||"}
REFSPEC_MAIN_RE = re.compile(r'(\borigin\s+main\b|:main\b|\brefs/heads/main\b)')
ENV_PREFIX_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')


def _tokenize_line(line):
    try:
        lex = shlex.shlex(line, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        # Unbalanced quote etc. -- never crash; treat the raw line as ONE
        # clause via a plain whitespace split (fail-safe, not fail-silent).
        tokens = line.split()
        return [tokens] if tokens else []
    clauses, current = [], []
    for tok in tokens:
        if tok in BOUNDARY_TOKENS:
            if current:
                clauses.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        clauses.append(current)
    return clauses


def _clauses(cmd):
    out = []
    for line in cmd.split("\n"):
        out.extend(_tokenize_line(line))
    return out


def _strip_env_prefix(tokens):
    i = 0
    while i < len(tokens) and ENV_PREFIX_RE.match(tokens[i]):
        i += 1
    return tokens[i:]


def classify(cmd):
    deny_gh_merge = deny_push_main = deny_promote_invocation = warn_wip = False
    for tokens in _clauses(cmd):
        t = _strip_env_prefix(tokens)
        if not t:
            continue
        head = t[0]
        if head == "gh" and len(t) >= 3 and t[1] == "pr" and t[2] == "merge":
            deny_gh_merge = True
        if (head in ("bash", "sh") and len(t) >= 2 and t[1].endswith("tools/promote.sh")) \
           or head.endswith("tools/promote.sh"):
            deny_promote_invocation = True
        if head == "git" and len(t) >= 2 and t[1] == "push":
            if REFSPEC_MAIN_RE.search(" ".join(t[2:])):
                deny_push_main = True
        if head == "git" and len(t) >= 2 and t[1] == "commit":
            if "-m" in t[2:] and any("WIP" in tok for tok in t[2:]):
                warn_wip = True
    return {
        "deny_gh_merge": deny_gh_merge,
        "deny_push_main": deny_push_main,
        "deny_promote_invocation": deny_promote_invocation,
        "warn_wip": warn_wip,
    }


try:
    raw_cmd = os.environ.get("_PTB_CMD", "")
    print(json.dumps(classify(raw_cmd)))
except Exception as exc:
    print(json.dumps({"error": str(exc)[:200]}))
PYEOF
)
_PTB_RC=$?

if [ $_PTB_RC -ne 0 ] || ! printf '%s' "$_PTB_JSON" | jq -e . >/dev/null 2>&1 \
   || printf '%s' "$_PTB_JSON" | jq -e 'has("error")' >/dev/null 2>&1; then
  emit_error_beacon "clause classifier failed (rc=$_PTB_RC) -- fail-open"
  exit 0
fi

_flag() { printf '%s' "$_PTB_JSON" | jq -r ".$1"; }

# `git push` targeting main via ANY refspec form (ADR-0076 D4 7c): plain
# `origin main`; `<src>:main` incl. `HEAD:main` and `:main` (delete-remote-main);
# or `refs/heads/main` (bare, or as a colon-form destination e.g.
# `HEAD:refs/heads/main`) -- matched ONLY within the same `git push` clause.
if [ "$(_flag deny_push_main)" = "true" ]; then
  emit_deny 'Direct push to main forbidden per CLAUDE.md rule #4 (all refspec forms denied: origin main, HEAD:main, refs/heads/main, :main); open a PR instead.'
fi

# `git commit -m "... WIP ..."` → warn-only (convention, not danger).
if [ "$(_flag warn_wip)" = "true" ]; then
  emit_warn 'WIP commit detected — CLAUDE.md rule #5 discourages WIP messages; prefer Conventional Commits.'
fi

# `tools/promote.sh` invoked (as the actual command) from a SUBAGENT context
# (ADR-0076 D4 7b) → deny. Reuses pre-tool-edit.sh's CLAUDE_AGENT_TYPE
# discriminator exactly: subagent contexts set this env var, the main-agent
# orchestrator does not. Promotion is a human-gated orchestrator action (see
# #880) — implementer.md and reviewer.md already prohibit it in prose; this
# makes the prohibition mechanical for subagent-context Bash invocations.
# Orchestrator-context invocations (no CLAUDE_AGENT_TYPE) fall through
# un-denied.
if [ "$(_flag deny_promote_invocation)" = "true" ] && [ -n "${CLAUDE_AGENT_TYPE:-}" ]; then
  emit_deny 'tools/promote.sh may not run from a subagent context — promotion is a human-gated orchestrator action (see #880); only the orchestrator invokes it directly.'
fi

# Raw `gh pr merge` (as the actual invocation) → DENY (ADR-0076 D4 7a;
# upgraded from the advisory warn added in PRD #1075 slice #1086). The
# sanctioned tools/pipe/pr-merge wrapper appends the atomic pr_merged v3 span
# a raw call skips, and asserts the reviewer APPROVE verdict (ADR-0076 D3) a
# raw call never checks. The wrapper invocation's clause head is `python`,
# never `gh` -- so this deny never fires on the sanctioned wrapper.
if [ "$(_flag deny_gh_merge)" = "true" ]; then
  emit_deny 'Raw `gh pr merge` denied — bypasses tools/pipe/pr-merge (no v3 pr_merged span, no APPROVE-verdict assertion). Use `python tools/pipe/pr-merge <PR>` instead.'
fi

exit 0
