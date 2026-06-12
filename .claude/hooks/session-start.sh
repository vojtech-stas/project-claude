#!/bin/bash
# session-start.sh — deterministic read-only session context injection.
#
# Implements ADR-0068 D3 (session-start context injection) + ADR-0057 D4.
# NEVER invokes skills or subagents (rule #12's hard line).
#
# What it injects:
#   - Branch name + divergence vs origin/main
#   - Recent commits (last 5)
#   - Open needs-human PRs/issues (I5 escalation surface)
#   - In-flight assigned slices
#   - Open PRs (recent 3)
#   - Open captured-queue depth
#   - Dashboard freshness (last /api/meta ping age in minutes)
#   - jq / hooks warnings
#
# Graceful degradation: missing gh → one-line warning, never block.
# Emits session_context_injected event via the canonical logger pattern.
#
# Fail-loud beacon contract per ADR-0057 D1: beacons attempt/ok/error.
# Output capped: 60 lines / 6KB.
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || true

# Resolve main root + LOG_DIR via lib-root.sh (beacon unification).
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
# shellcheck source=lib-root.sh
source "$SCRIPT_DIR/lib-root.sh"

# Read stdin ONCE before any work (SessionStart passes JSON on stdin).
SESSION_STDIN=$(cat)

# Beacon ATTEMPT before any work (fail-loud contract per ADR-0057 D1).
printf '{"hook":"session-start","status":"attempt","ts":"%s"}\n' \
  "$(date -Iseconds 2>/dev/null)" \
  >> "$LOG_DIR/hook-fires.jsonl" 2>/dev/null || true

# Python3 in-hook self-test: beacon result so interpreter liveness is explicit.
_PY3_STATUS="ok"
python3 -c "import json,sys" 2>/dev/null || _PY3_STATUS="error"
printf '{"hook":"session-start","status":"python3_selftest","result":"%s","ts":"%s"}\n' \
  "$_PY3_STATUS" "$(date -Iseconds 2>/dev/null)" \
  >> "$LOG_DIR/hook-fires.jsonl" 2>/dev/null || true

# ---- git state (always available) ------------------------------------------
BR=$(git symbolic-ref --short HEAD 2>/dev/null || echo "(detached)")
DIV="(fetch failed)"
git fetch origin main 2>/dev/null && DIV=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "?")
LOG=$(git log --oneline -5 2>/dev/null || echo "(no log)")

# ---- hooks path warning -------------------------------------------------------
HOOKS_WARN=""
if command -v git >/dev/null 2>&1; then
  HOOKS=$(git config --get core.hooksPath 2>/dev/null || echo "__unset__")
  if [ "$HOOKS" != ".githooks" ]; then
    HOOKS_WARN=$(printf "\n*** WARNING: git core.hooksPath is not '.githooks' (got: %s). Fix: run ./.githooks/install.sh ***\n" "$HOOKS")
  fi
fi

# ---- gh/jq availability -------------------------------------------------------
JQ_OK=0; GH_OK=0
command -v jq >/dev/null 2>&1 && JQ_OK=1
[ "$JQ_OK" -eq 1 ] && command -v gh >/dev/null 2>&1 \
  && gh auth status >/dev/null 2>&1 && GH_OK=1

# ---- jq warning ---------------------------------------------------------------
JQ_WARN=""
if [ "$JQ_OK" -ne 1 ]; then
  JQ_WARN=$(printf "\nWARNING: jq missing. PreToolUse Edit/Write hook degrades to rule-#10 ask. Install: bootstrap.sh or winget/brew/apt jq.\n")
fi

# ---- gh-unavailable warning ---------------------------------------------------
GH_WARN=""
if [ "$GH_OK" -ne 1 ]; then
  GH_WARN=$(printf "\nWARNING: gh CLI unavailable or not authenticated. Issue/PR state unavailable at session start.\n")
fi

# ---- GitHub live state (gh + jq required) ------------------------------------
q_label() {
  gh issue list --label "$1" --state open --json number,title --limit 3 2>/dev/null \
    | jq -r 'if length==0 then "0 open"
             else "\(length)+ open; recent: \([.[] | "#\(.number) \(.title)"] | join(" | "))"
             end' 2>/dev/null || echo "(query failed)"
}

NH_ISSUES="(gh/jq unavailable)"
NH_PRS="(gh/jq unavailable)"
SL="(gh/jq unavailable)"
PR="(gh/jq unavailable)"
CAP="(gh/jq unavailable)"
DASH_FRESH="(not checked)"

if [ "$GH_OK" -eq 1 ]; then
  NH_ISSUES=$(q_label needs-human)
  SL=$(q_label slice)
  CAP=$(q_label captured)
  PR=$(gh pr list --state open --json number,title --limit 3 2>/dev/null \
       | jq -r 'if length==0 then "0 open"
                else "\(length)+ open; recent: \([.[] | "#\(.number) \(.title)"] | join(" | "))"
                end' 2>/dev/null || echo "(query failed)")
  NH_PRS=$(gh pr list --state open --label needs-human --json number,title --limit 3 2>/dev/null \
           | jq -r 'if length==0 then "0 needs-human PRs"
                    else "\(length)+ needs-human PRs: \([.[] | "#\(.number) \(.title)"] | join(" | "))"
                    end' 2>/dev/null || echo "(query failed)")
fi

# ---- Dashboard freshness (no gh required) -----------------------------------
if command -v python3 >/dev/null 2>&1; then
  DASH_FRESH=$(python3 -c "
import urllib.request, json, datetime, sys
try:
    resp = urllib.request.urlopen('http://localhost:8765/api/meta', timeout=2)
    data = json.loads(resp.read())
    ts = data.get('ts', '')
    if ts:
        dt = datetime.datetime.fromisoformat(ts.replace('Z', '+00:00'))
        age_m = int((datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() / 60)
        print(f'dashboard up ({age_m}m since last sync)')
    else:
        print('dashboard up (no ts in /api/meta)')
except Exception as e:
    print(f'dashboard unreachable ({e})')
" 2>/dev/null || echo "(check failed)")
fi

# ---- Build context string ---------------------------------------------------
CTX=$(printf "Branch: %s | %s commit(s) behind origin/main\n\nRecent commits:\n%s\n\nNeeds-human issues: %s\nNeeds-human PRs: %s\nOpen slices: %s\nOpen PRs: %s\nOpen captured: %s\nDashboard: %s%s%s%s\n" \
  "$BR" "$DIV" "$LOG" \
  "$NH_ISSUES" "$NH_PRS" "$SL" "$PR" "$CAP" "$DASH_FRESH" \
  "$HOOKS_WARN" "$JQ_WARN" "$GH_WARN" \
  | head -c 6144 | head -n 60)

# ---- Emit session_context_injected event via canonical logger pattern --------
export LTE_STDIN="$SESSION_STDIN"
export LTE_EVENT_TYPE="session_context_injected"
export LTE_LOG_DIR="$LOG_DIR"

python3 - <<'PYEOF'
import sys, os, json, datetime, re, subprocess

event_type = "session_context_injected"
log_dir    = os.environ["LTE_LOG_DIR"]
stdin_data = os.environ.get("LTE_STDIN", "")

def ts_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def beacon(status, reason=None):
    obj = {"hook": event_type, "status": status, "ts": ts_now()}
    if reason:
        obj["reason"] = reason
    line = json.dumps(obj, separators=(",", ":"))
    target = os.environ.get("WORKFLOW_LOG_DIR", log_dir)
    os.makedirs(target, exist_ok=True)
    try:
        with open(os.path.join(target, "hook-fires.jsonl"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass  # never crash

FIXTURE_PATTERN = re.compile(
    r"^(demo|test|verify|fixture|manual|sess-|sample-session-id$)",
    re.IGNORECASE
)

try:
    raw = stdin_data.strip()
    if not raw:
        raise ValueError("empty stdin")
    payload = json.loads(raw)
    session_id = payload.get("session_id", "")
    if not session_id:
        raise ValueError("missing or empty session_id")

    # Derive worktree name from git toplevel basename.
    try:
        toplevel = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL, timeout=3
        ).decode().strip()
        wt = os.path.basename(toplevel) if toplevel else "unknown"
    except Exception:
        wt = "unknown"

    event = {
        "v": 2,
        "ts": ts_now(),
        "session_id": session_id,
        "src": "hook",
        "wt": wt,
        "event": event_type,
    }
    line = json.dumps(event, separators=(",", ":"))

    sandbox = os.environ.get("WORKFLOW_LOG_DIR", "")
    write_dir = sandbox if sandbox else log_dir
    is_fixture = bool(FIXTURE_PATTERN.match(session_id))
    target_file = "workflow-events.test.jsonl" if is_fixture else "workflow-events.jsonl"

    os.makedirs(write_dir, exist_ok=True)
    with open(os.path.join(write_dir, target_file), "a", encoding="utf-8") as f:
        f.write(line + "\n")

    beacon("ok")

except Exception as exc:
    reason = str(exc)[:200]
    reject_dir = os.environ.get("WORKFLOW_LOG_DIR", log_dir)
    os.makedirs(reject_dir, exist_ok=True)
    reject_obj = {
        "ts": ts_now(),
        "hook": event_type,
        "reason": reason,
        "raw": stdin_data[:4096],
    }
    try:
        with open(os.path.join(reject_dir, "workflow-events.rejects.jsonl"),
                  "a", encoding="utf-8") as f:
            f.write(json.dumps(reject_obj, separators=(",", ":")) + "\n")
    except Exception:
        pass
    beacon("error", reason)
PYEOF

# ---- Emit hookSpecificOutput to stdout ---------------------------------------
if [ "$JQ_OK" -eq 1 ]; then
  jq -cn --arg ctx "$CTX" \
    '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
else
  ESC=$(printf '%s' "$CTX" \
        | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' \
        | awk 'BEGIN{ORS="\\n"}{print}')
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$ESC"
fi

# Beacon OK at the end.
printf '{"hook":"session-start","status":"ok","ts":"%s"}\n' \
  "$(date -Iseconds 2>/dev/null)" \
  >> "$LOG_DIR/hook-fires.jsonl" 2>/dev/null || true

exit 0
