#!/bin/bash
# log-tool-event.sh — parameterized python3-based hook logger (PRD #668 slice #669).
#
# CONTRACT:
#   Called with exactly one argument: the event_type string
#   (e.g. session_start, session_stop).
#   Hook stdin is a JSON object from Claude Code containing session_id,
#   hook_event_name, and event-specific fields.
#
# ORDERING GUARANTEE (per PRD #668 §2 / rabbit-holes):
#   1. Read stdin once into a bash variable.
#   2. BEACON attempt → hook-fires.jsonl  (pure bash — no parse dependency).
#   3. Parse + validate with python3.
#   4. Route + write v2 event to workflow-events[.test].jsonl OR rejects.
#   5. BEACON ok|error.
#   6. Exit 0 always (never break the session).
#
# ROUTING:
#   - If WORKFLOW_LOG_DIR env is set → write under that dir (test harness sandbox).
#   - fixture session_id (matches FIXTURE_PATTERN) → workflow-events.test.jsonl.
#   - else → workflow-events.jsonl (production).
#   The two routing dimensions are independent: sandbox dir + fixture file name
#   can both apply simultaneously.
#
# Schema v2: {"v":2, "ts", "session_id" (required/non-empty), "src":"hook",
#              "wt":<basename of git toplevel>, "event", ...payload}
#
# NO jq IN THIS FILE — python3 only; jq ENOEXEC hazard is structurally irrelevant.
#
# Invoke style (settings.json registration):
#   bash "$CLAUDE_PROJECT_DIR/.claude/hooks/log-tool-event.sh" session_start

EVENT_TYPE="${1:-unknown}"

# Step 1: read stdin once into a bash variable.
LTE_STDIN=$(cat)

# Step 2: beacon ATTEMPT before any parsing — pure bash, no parse dependency.
# Source lib-root.sh to get LOG_DIR (and MAIN_ROOT).
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
# shellcheck source=lib-root.sh
source "$SCRIPT_DIR/lib-root.sh"

# Write attempt beacon (pure bash printf — no jq, no python).
printf '{"hook":"%s","status":"attempt","ts":"%s"}\n' \
  "$EVENT_TYPE" "$(date -Iseconds 2>/dev/null)" \
  >> "$LOG_DIR/hook-fires.jsonl" 2>/dev/null || true

# Steps 3-5: parse, validate, route, write, beacon result — via python3.
# Pass stdin content via env var (stdin is already consumed above).
export LTE_STDIN
export LTE_EVENT_TYPE="$EVENT_TYPE"
export LTE_LOG_DIR="$LOG_DIR"

python3 - <<'PYEOF'
import sys, os, json, datetime, re, subprocess

event_type = os.environ["LTE_EVENT_TYPE"]
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
    r"^(demo|test|verify|fixture|manual|sess-)",
    re.IGNORECASE
)

def is_fixture_sid(sid):
    return bool(FIXTURE_PATTERN.match(sid))

try:
    raw = stdin_data.strip()
    if not raw:
        raise ValueError("empty stdin")

    payload = json.loads(raw)

    # Validate required field.
    session_id = payload.get("session_id", "")
    if not session_id:
        raise ValueError("missing or empty session_id")

    # Derive worktree name from git toplevel basename.
    try:
        toplevel = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            timeout=3
        ).decode().strip()
        wt = os.path.basename(toplevel) if toplevel else "unknown"
    except Exception:
        wt = "unknown"

    # Build v2 event.
    event = {
        "v": 2,
        "ts": ts_now(),
        "session_id": session_id,
        "src": "hook",
        "wt": wt,
        "event": event_type,
    }

    # Selected payload fields (session_start / session_stop carry no extra
    # payload in this slice; slices 2-3 will add agent/bash fields).

    line = json.dumps(event, separators=(",", ":"))

    # Routing (two independent dimensions):
    # - WORKFLOW_LOG_DIR overrides the base directory (test harness sandbox).
    # - fixture session_id always routes to workflow-events.test.jsonl.
    sandbox = os.environ.get("WORKFLOW_LOG_DIR", "")
    write_dir = sandbox if sandbox else log_dir
    target_file = "workflow-events.test.jsonl" if is_fixture_sid(session_id) else "workflow-events.jsonl"

    os.makedirs(write_dir, exist_ok=True)
    with open(os.path.join(write_dir, target_file), "a", encoding="utf-8") as f:
        f.write(line + "\n")

    beacon("ok")

except Exception as exc:
    reason = str(exc)[:200]
    # Preserve raw stdin in rejects file (lossless).
    reject_dir = os.environ.get("WORKFLOW_LOG_DIR", log_dir)
    os.makedirs(reject_dir, exist_ok=True)
    reject_obj = {
        "ts": ts_now(),
        "hook": event_type,
        "reason": reason,
        "raw": stdin_data[:4096],
    }
    try:
        with open(os.path.join(reject_dir, "workflow-events.rejects.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(reject_obj, separators=(",", ":")) + "\n")
    except Exception:
        pass
    beacon("error", reason)
PYEOF

exit 0
