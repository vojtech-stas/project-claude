#!/usr/bin/env python3
"""
dashboard/server.py — project-claude workflow dashboard server.

Serves: GET /               -> dashboard/index.html
        GET /api/architecture -> JSON {skills, agents, hooks, adrs, edges}
        GET /api/pipeline     -> JSON pipeline spec (SPEC v2 from pipeline_spec.py)
        GET /api/health       -> JSON {auditMeta, auditSubagents, cascadeFinder}
        GET /api/file?path=   -> file content (path-traversal safe)
        GET /api/runs?n=N     -> last-N run metadata (no events) grouped by session_id
        GET /api/runs?before=<session_id> -> older runs cursor (metadata-only)
        GET /api/runs?session=<id> -> one session's full events as {run:{...events:[]}}
        GET /api/workitems        -> JSON {prd:[...], slices:[...], prs:[...], captures:[...], backlog:[...]} via gh CLI (30s cache)
        GET /api/live-progress    -> JSON Lane A run-progress for most recent open PRD (25s TTL bg-thread cache)
        GET /api/live-poll?cursor=N -> JSON {cursor, events[], reset} — byte-cursor incremental read (Lane B)
        GET /api/trail?prd=N      -> JSON artifact trail for PRD #N (cache-first, ADR-0053 D1/D4)
        GET /api/comparison?prd=N -> JSON per-run comparison report for PRD #N (ADR-0053 D3)
        GET /api/trail-runs?last=N -> JSON list of last N closed PRDs (for run picker)
        GET /api/rollup?last=N    -> JSON repo rollup over last N closed PRDs (ADR-0053 D3)

Start: python dashboard/server.py
Config: DASH_PORT env var (default 8765)
Requires: Python 3 stdlib only — no pip install needed.
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# Repo root — server.py lives at <repo>/dashboard/server.py
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"

# ---------------------------------------------------------------------------
# Trail module imports — explicit named imports (never import *).
# sys.path injection keeps imports working both when:
#   (a) server.py is run as __main__ (dashboard/ is cwd or on path)
#   (b) server.py is imported by CHECK 9 (cwd is repo root)
# ---------------------------------------------------------------------------
_DASHBOARD_DIR_STR = str(Path(__file__).resolve().parent)
if _DASHBOARD_DIR_STR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR_STR)

from collector import get_trail, get_closed_prd_numbers, rollup  # noqa: E402
from comparison import compare, get_spec_for_compare  # noqa: E402
from pipeline_spec import get_spec as _get_pipeline_spec  # noqa: E402

# ---------------------------------------------------------------------------
# Rollup cache — rollup calls gh CLI per-PR so it can take 20-40s on cold
# start; keyed by last_n with 120s TTL.  Background-thread computation so
# the HTTP handler returns immediately with {"status":"computing"} while the
# work runs; client polls until status transitions to "ready".
# ---------------------------------------------------------------------------
_rollup_cache: dict = {}        # {last_n: {"data": {...}, "ts": float}}
_rollup_computing: dict = {}    # {last_n: True} — in-flight marker
_rollup_lock = threading.Lock()
_ROLLUP_CACHE_TTL = 120    # seconds


def _rollup_background(last_n: int) -> None:
    """Compute rollup in a background thread and store result in _rollup_cache."""
    try:
        spec = get_spec_for_compare()
        result = rollup(last_n=last_n, compare_fn=compare, spec=spec)
        with _rollup_lock:
            _rollup_cache[last_n] = {"data": result, "ts": time.time()}
    except Exception as e:
        # Store error so polling can surface it
        with _rollup_lock:
            _rollup_cache[last_n] = {
                "data": {"status": "error", "error": str(e)},
                "ts": time.time(),
            }
    finally:
        with _rollup_lock:
            _rollup_computing.pop(last_n, None)


# ---------------------------------------------------------------------------
# Live-progress cache — resolves the most recent open PRD + reads its trail.
# Background-thread + 25s TTL, exactly like /api/rollup.  NO gh calls in the
# HTTP handler.
# ---------------------------------------------------------------------------
_live_progress_cache: dict = {}   # {"data": {...}, "ts": float}
_live_progress_computing: bool = False
_live_progress_lock = threading.Lock()
_LIVE_PROGRESS_TTL = 25           # seconds

_WORKFLOW_LOG = REPO_ROOT / ".claude" / "logs" / "workflow-events.jsonl"
_CAPTURE_PILL_THRESHOLD = 120     # seconds — coarse freshness threshold

# Reader-side fixture-pattern guard (mirrors log-tool-event.sh FIXTURE_PATTERN).
_FIXTURE_SID_RE_POLL = re.compile(
    r"^(demo|test|verify|fixture|manual|sess-)", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# /api/live-poll — byte-cursor incremental read of workflow-events.jsonl.
# O(appended bytes) per poll; file identity = (size, mtime) tuple.
# ---------------------------------------------------------------------------

def _live_poll_log_path() -> Path:
    """Return the workflow-events.jsonl path, honouring WORKFLOW_LOG_DIR sandbox."""
    override = os.environ.get("WORKFLOW_LOG_DIR", "")
    if override:
        return Path(override) / "workflow-events.jsonl"
    return _WORKFLOW_LOG


def serve_live_poll(cursor_raw: str) -> dict:
    """Stat the log, seek to cursor, parse only appended bytes.

    Returns {cursor: int, events: list, reset: bool}.
    File identity = (size, mtime) tuple — st_ino is unreliable on Windows.
    Identity change or size < cursor → reset cursor to 0, reset:true.
    """
    log_path = _live_poll_log_path()
    if not log_path.exists():
        return {"cursor": 0, "events": [], "reset": False}

    try:
        cursor = int(cursor_raw)
    except (TypeError, ValueError):
        cursor = 0

    try:
        st = log_path.stat()
        size = st.st_size
        mtime = st.st_mtime
    except OSError:
        return {"cursor": 0, "events": [], "reset": False}

    # File identity encoded in cursor: we embed (mtime_int, byte_offset) as a
    # single opaque integer only on the server side. Simpler: just use raw byte
    # offset and detect resets by size < cursor (truncation) or caller passing 0.
    reset = False
    if cursor < 0 or cursor > size:
        # Truncation or cursor from a different file lifetime → full re-read
        cursor = 0
        reset = True

    if cursor == size:
        # Nothing new
        return {"cursor": cursor, "events": [], "reset": reset}

    try:
        with log_path.open("rb") as fh:
            fh.seek(cursor)
            chunk = fh.read(size - cursor)
    except OSError:
        return {"cursor": cursor, "events": [], "reset": reset}

    new_cursor = cursor + len(chunk)
    text = chunk.decode("utf-8", errors="replace")
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        # Schema-v2 only; drop fixture sids silently
        if obj.get("v") != 2:
            continue
        sid = obj.get("session_id", "")
        if not sid:
            continue
        if _FIXTURE_SID_RE_POLL.match(sid):
            continue
        events.append(obj)

    return {"cursor": new_cursor, "events": events, "reset": reset}


def _capture_pill_state() -> dict:
    """Compute capture pill state from workflow-events.jsonl freshness.

    Returns {"state": "LIVE"|"INACTIVE", "label": str, "last_event_s": float|None}.
    """
    try:
        if not _WORKFLOW_LOG.exists():
            return {
                "state": "INACTIVE",
                "label": (
                    "INACTIVE — this session never registered hooks "
                    "(known Claude Code behavior on resumed sessions); "
                    "run progress is artifact-based"
                ),
                "last_event_s": None,
            }
        # Find the most recent v2 event timestamp by reading last 16 KiB
        size = _WORKFLOW_LOG.stat().st_size
        chunk_size = min(16384, size)
        with _WORKFLOW_LOG.open("rb") as fh:
            fh.seek(max(0, size - chunk_size))
            raw = fh.read(chunk_size)
        lines = raw.decode("utf-8", errors="replace").splitlines()
        last_ts_str = None
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("v") == 2 and obj.get("ts"):
                last_ts_str = obj["ts"]
                break
        if last_ts_str is None:
            return {
                "state": "INACTIVE",
                "label": (
                    "INACTIVE — this session never registered hooks "
                    "(known Claude Code behavior on resumed sessions); "
                    "run progress is artifact-based"
                ),
                "last_event_s": None,
            }
        # Parse timestamp
        ts_epoch = None
        try:
            import datetime as _dt
            ts_epoch = _dt.datetime.fromisoformat(
                last_ts_str.replace("Z", "+00:00")
            ).timestamp()
        except Exception:
            pass
        if ts_epoch is None:
            return {"state": "INACTIVE", "label": "INACTIVE — timestamp parse error",
                    "last_event_s": None}
        age_s = time.time() - ts_epoch
        if age_s < _CAPTURE_PILL_THRESHOLD:
            return {
                "state": "LIVE",
                "label": f"LIVE — last event {int(age_s)}s ago",
                "last_event_s": age_s,
            }
        return {
            "state": "INACTIVE",
            "label": (
                "INACTIVE — this session never registered hooks "
                "(known Claude Code behavior on resumed sessions); "
                "run progress is artifact-based"
            ),
            "last_event_s": age_s,
        }
    except Exception as exc:
        return {"state": "INACTIVE", "label": f"INACTIVE — read error: {exc}",
                "last_event_s": None}


def _resolve_open_prd() -> int | None:
    """Return the issue number of the most recent open prd-labeled issue.

    Uses gh CLI; returns None on any error.
    """
    try:
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--label", "prd",
                "--state", "open",
                "--limit", "1",
                "--json", "number",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            cwd=str(REPO_ROOT),
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            return None
        items = json.loads(result.stdout)
        if not items:
            return None
        return items[0]["number"]
    except Exception:
        return None


def _build_live_progress() -> dict:
    """Fetch the most recent open PRD trail and shape the live-progress payload.

    Called from the background thread; never from an HTTP handler.
    """
    pill = _capture_pill_state()
    prd_number = _resolve_open_prd()
    if prd_number is None:
        return {
            "prd_number": None,
            "prd_title": None,
            "slices": [],
            "collector_status": {"state": "ok", "label": "No open PRD"},
            "capture_pill": pill,
        }

    trail = get_trail(prd_number)
    _cs_raw = trail.get("collector_status", "")
    if not _cs_raw:
        collector_status = {"state": "ok", "label": "Collector OK"}
    elif _cs_raw == "auth_dead":
        collector_status = {"state": "auth_dead", "label": "auth_dead — gh CLI unauthenticated"}
    else:
        collector_status = {"state": "offline", "label": f"OFFLINE — showing cached trails ({_cs_raw})"}

    slices_out = []
    for sl in trail.get("slices", []):
        sl_num = sl.get("number")
        pr_num = sl.get("closing_pr_number")
        pr_info = trail.get("prs", {}).get(str(pr_num)) if pr_num else None

        if sl.get("closed_at"):
            stage = "closed"
        elif pr_num and pr_info and pr_info.get("merged_at"):
            stage = "pr_merged"
        elif pr_num:
            stage = "pr_open"
        elif sl.get("assignees"):
            stage = "assigned"
        else:
            stage = "open"

        last_verdict = None
        verdict_rounds = 0
        if pr_info:
            last_verdict = pr_info.get("last_verdict")
            verdict_rounds = pr_info.get("verdict_count", 0)

        slices_out.append({
            "number": sl_num,
            "title": sl.get("title", ""),
            "stage": stage,
            "pr_number": pr_num,
            "pr_merged_at": pr_info.get("merged_at") if pr_info else None,
            "pr_created_at": pr_info.get("created_at") if pr_info else None,
            "slice_created_at": sl.get("created_at"),
            "slice_closed_at": sl.get("closed_at"),
            "verdict_rounds": verdict_rounds,
            "last_verdict": last_verdict,
            "assignees": sl.get("assignees", []),
        })

    return {
        "prd_number": prd_number,
        "prd_title": trail.get("prd_title", f"PRD #{prd_number}"),
        "prd_created_at": trail.get("prd_created_at"),
        "slices": slices_out,
        "collector_status": collector_status,
        "capture_pill": pill,
    }


def _live_progress_background() -> None:
    """Compute live-progress in a background thread and cache the result."""
    global _live_progress_computing
    try:
        result = _build_live_progress()
        with _live_progress_lock:
            _live_progress_cache["data"] = result
            _live_progress_cache["ts"] = time.time()
    except Exception as e:
        with _live_progress_lock:
            _live_progress_cache["data"] = {
                "error": str(e),
                "collector_status": "error",
                "capture_pill": {"state": "INACTIVE", "label": "INACTIVE — error"},
            }
            _live_progress_cache["ts"] = time.time()
    finally:
        with _live_progress_lock:
            _live_progress_computing = False


def _resolve_invoking_repo_root() -> Path:
    """Resolve the repo root from the INVOKING worktree's cwd.

    Used by --generate-readme so the generator writes into the worktree that
    invoked it (not the worktree where server.py physically lives, which may be
    a sibling worktree on a different branch).

    Resolution order:
      1. git rev-parse --show-toplevel (run from cwd — worktree-aware)
      2. $CLAUDE_PROJECT_DIR env var
      3. Path(__file__).resolve().parent.parent (script-file fallback)
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=os.getcwd(),
        )
        if result.returncode == 0:
            root = Path(result.stdout.strip())
            if root.is_dir():
                return root
    except Exception:
        pass

    claude_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if claude_dir:
        p = Path(claude_dir)
        if p.is_dir():
            return p

    return Path(__file__).resolve().parent.parent

# Known critics (explicit allow-list per implementer note 1).
# 7 critics per ADR-0046 D1 (parsimony principle; codebase-critic added ADR-0046 D2).
KNOWN_CRITICS = {
    "reviewer",
    "prd-critic",
    "adr-critic",
    "slicer-critic",
    "glossary-critic",
    "backlog-critic",
    "codebase-critic",
}


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter fields from a markdown file (name, description, role)."""
    fields = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            return fields
        end = text.find("\n---", 3)
        if end == -1:
            return fields
        fm_block = text[3:end]
        for line in fm_block.splitlines():
            m = re.match(r'^(\w+):\s*(.+)$', line.strip())
            if m:
                fields[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    except Exception:
        pass
    return fields


KNOWN_GENERATORS = {
    "slicer",
    "implementer",
    "qa-tester",
}


def _classify_agent(stem: str, description: str) -> str:
    """Classify an agent as 'critic' or 'generator'.

    Priority: explicit allow-lists first (both directions), then description heuristic.
    slicer is a generator even though its description mentions 'slicer-critic'.
    """
    if stem in KNOWN_GENERATORS:
        return "generator"
    if stem in KNOWN_CRITICS:
        return "critic"
    # Description heuristic: look for standalone 'critic' word, not substring of another token
    if re.search(r'\bcritic\b', description.lower()):
        return "critic"
    return "generator"


def discover_skills() -> list:
    skills_dir = REPO_ROOT / ".claude" / "skills"
    skills = []
    if not skills_dir.exists():
        return skills
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        fm = _parse_frontmatter(skill_md)
        skills.append({
            "name": fm.get("name", skill_md.parent.name),
            "description": fm.get("description", ""),
            # Fix A: use .as_posix() so paths are forward-slash on Windows
            "path": skill_md.relative_to(REPO_ROOT).as_posix(),
        })
    return skills


def discover_agents() -> list:
    agents_dir = REPO_ROOT / ".claude" / "agents"
    agents = []
    if not agents_dir.exists():
        return agents
    for agent_md in sorted(agents_dir.glob("*.md")):
        fm = _parse_frontmatter(agent_md)
        stem = agent_md.stem
        description = fm.get("description", "")
        kind = _classify_agent(stem, description)
        agents.append({
            "name": fm.get("name", stem),
            "stem": stem,
            "type": kind,
            "description": description,
            # Fix A: use .as_posix() so paths are forward-slash on Windows
            "path": agent_md.relative_to(REPO_ROOT).as_posix(),
        })
    return agents


def _read_hook_description(cmd: str) -> str:
    """Derive a human-readable description for a hook command.

    For .sh-script hooks: read the script's leading comment block (lines after
    the shebang that start with '#').  For inline jq/bash commands: derive a
    short string from the command pattern.
    """
    # .sh script reference: read the script's leading comment block
    m = re.search(r'hooks/([a-z0-9_-]+\.sh)', cmd)
    if m:
        script_path = REPO_ROOT / ".claude" / "hooks" / m.group(1)
        if script_path.exists():
            try:
                lines = script_path.read_text(encoding="utf-8", errors="replace").splitlines()
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("#!"):
                        continue  # skip shebang
                    if stripped.startswith("#"):
                        text = stripped.lstrip("#").strip()
                        if text:
                            return text[:100]
                    elif stripped:
                        break  # end of leading comment block
            except Exception:
                pass

    # Inline command patterns: derive description from content
    cmd_lower = cmd.lower()
    if "workflow-events.jsonl" in cmd_lower and "agent_start" in cmd_lower:
        return "logs agent start events to workflow-events.jsonl"
    if "workflow-events.jsonl" in cmd_lower and "agent_complete" in cmd_lower:
        return "logs agent completions to workflow-events.jsonl"
    if "workflow-events.jsonl" in cmd_lower and "bash_complete" in cmd_lower:
        return "logs bash completions to workflow-events.jsonl"
    if "workflow-events.jsonl" in cmd_lower and "session_stop" in cmd_lower:
        return "logs session-stop event to workflow-events.jsonl"
    if "subagent-edits.log" in cmd_lower:
        return "logs agent file edits; suggests /audit-subagents on agent .md changes"
    if "workflow-events.jsonl" in cmd_lower:
        return "logs workflow event to workflow-events.jsonl"

    # Fallback: truncated raw command
    return cmd[:80]


def _read_hook_name(cmd: str) -> str:
    """Derive a short human-readable name for a hook command.

    For .sh-script hooks: returns the filename stem (e.g. 'session-start').
    For inline hooks: returns a concise label matching the event logged.
    """
    # .sh script reference: use the filename stem
    m = re.search(r'hooks/([a-z0-9_-]+)\.sh', cmd)
    if m:
        return m.group(1)

    # Inline command patterns: derive clean name from content
    cmd_lower = cmd.lower()
    if "workflow-events.jsonl" in cmd_lower and "agent_start" in cmd_lower:
        return "agent_start logger"
    if "workflow-events.jsonl" in cmd_lower and "agent_complete" in cmd_lower:
        return "agent_complete logger"
    if "workflow-events.jsonl" in cmd_lower and "bash_complete" in cmd_lower:
        return "bash logger"
    if "workflow-events.jsonl" in cmd_lower and "session_stop" in cmd_lower:
        return "session_stop logger"
    if "workflow-events.jsonl" in cmd_lower and "skill_invoke" in cmd_lower:
        return "skill_invoke logger"
    if "workflow-events.jsonl" in cmd_lower and "grill_qa" in cmd_lower:
        return "grill_qa logger"
    if "subagent-edits.log" in cmd_lower:
        return "subagent-edit nudge"
    if "workflow-events.jsonl" in cmd_lower:
        return "workflow event logger"

    # Fallback: short truncation (not full raw command)
    return cmd[:30].strip()


def _read_hook_purpose(cmd: str) -> str:
    """Return the header-comment block of a hook script (slice #628).

    Reads all contiguous '#'-prefixed lines after the shebang line, before
    the first non-comment non-blank line.  Strips leading '# ' / '#' from
    each line, joins with newlines, truncates to 800 chars.
    Fail-soft: returns "" if the script has no header comment or cannot be read.
    """
    m = re.search(r'hooks/([a-z0-9_-]+\.sh)', cmd)
    if not m:
        return ""
    script_path = REPO_ROOT / ".claude" / "hooks" / m.group(1)
    if not script_path.exists():
        return ""
    try:
        lines = script_path.read_text(encoding="utf-8", errors="replace").splitlines()
        comment_lines: list[str] = []
        past_shebang = False
        for line in lines:
            stripped = line.strip()
            if not past_shebang and stripped.startswith("#!"):
                past_shebang = True
                continue
            if stripped.startswith("#"):
                text = stripped[1:].lstrip(" ")
                comment_lines.append(text)
            elif stripped == "":
                # blank lines inside header are included; stop on non-blank non-comment
                if comment_lines:
                    comment_lines.append("")
            else:
                break  # first non-comment non-blank line — header block ends
        # Strip trailing blank lines accumulated at the end
        while comment_lines and comment_lines[-1] == "":
            comment_lines.pop()
        purpose = "\n".join(comment_lines)
        return purpose[:800]
    except Exception:
        return ""


def _read_hook_fire_telemetry() -> dict:
    """Read hook-fires.jsonl and aggregate per-event-type fire_count + error_count + last_fired.

    Keys telemetry on the event-type name carried in each beacon's ``hook`` field
    (e.g. session_start, agent_complete) — distinct per-event-type entries instead
    of one shared bucket per script file.

    fire_count  = attempt beacons (status == "attempt" or no status field on legacy lines).
    error_count = error beacons (status == "error").
    last_fired  = most recent ts across all beacons for that event type.

    Reads only the last ~5000 lines to avoid unbounded growth becoming slow.
    Fail-soft: returns empty dict on any error (every event type will show 0/null).
    """
    beacon_path = REPO_ROOT / ".claude" / "logs" / "hook-fires.jsonl"
    telemetry: dict = {}
    if not beacon_path.exists():
        return telemetry
    try:
        # Read last ~5000 lines only
        text = beacon_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        lines = lines[-5000:] if len(lines) > 5000 else lines
        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            event_name = obj.get("hook", "")
            ts = obj.get("ts", "")
            status = obj.get("status", "")
            if not event_name:
                continue
            entry = telemetry.setdefault(
                event_name,
                {"fire_count": 0, "error_count": 0, "last_fired": None},
            )
            # fire_count: attempt beacons; legacy lines (no status) also count as attempts.
            if status in ("attempt", ""):
                entry["fire_count"] += 1
            elif status == "error":
                entry["error_count"] += 1
            if ts and (entry["last_fired"] is None or ts > entry["last_fired"]):
                entry["last_fired"] = ts
    except Exception:
        pass
    return telemetry


def _event_type_from_cmd(cmd: str) -> str:
    """Extract the event-type argument from a log-tool-event.sh command string.

    Commands look like: bash "...log-tool-event.sh" session_start
    Returns the event-type token (e.g. "session_start") if present, else "".
    This is used as the telemetry key so each registered event type gets its own
    distinct fire_count / error_count bucket instead of collapsing under the script
    file name.
    """
    m = re.search(r'log-tool-event\.sh["\s]+([a-z_]+)', cmd)
    if m:
        return m.group(1)
    return ""


def discover_hooks() -> list:
    settings_path = REPO_ROOT / ".claude" / "settings.json"
    hooks = []
    if not settings_path.exists():
        return hooks
    telemetry = _read_hook_fire_telemetry()
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        for event, entries in data.get("hooks", {}).items():
            for entry in entries:
                matcher = entry.get("matcher", "")
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    # Extract script name; resolve to actual .sh path when available (Fix C)
                    m = re.search(r'hooks/([a-z0-9_-]+\.sh)', cmd)
                    if m:
                        script_name = m.group(1)
                        name = script_name
                        script_path = REPO_ROOT / ".claude" / "hooks" / script_name
                        hook_path = (
                            f".claude/hooks/{script_name}"
                            if script_path.exists()
                            else ".claude/settings.json"
                        )
                    else:
                        name = cmd[:60]
                        hook_path = ".claude/settings.json"
                    clean_name = _read_hook_name(cmd)
                    # For log-tool-event.sh registrations, use the event-type argument
                    # as the telemetry key so each event type gets its own distinct bucket
                    # (session_start, agent_complete, …) instead of collapsing under the
                    # shared script stem "log-tool-event".
                    event_type_arg = _event_type_from_cmd(cmd)
                    telemetry_key = event_type_arg if event_type_arg else clean_name
                    fire_data = telemetry.get(
                        telemetry_key,
                        {"fire_count": 0, "error_count": 0, "last_fired": None},
                    )
                    hooks.append({
                        "name": telemetry_key if event_type_arg else clean_name,
                        "clean_name": telemetry_key if event_type_arg else clean_name,
                        "event": event,
                        "matcher": matcher,
                        "command": cmd[:120],
                        "description": _read_hook_description(cmd),  # Fix C
                        "path": hook_path,  # Fix C: resolved .sh path
                        "purpose": _read_hook_purpose(cmd),  # slice #628
                        "fire_count": fire_data["fire_count"],
                        "error_count": fire_data.get("error_count", 0),
                        "last_fired": fire_data["last_fired"],
                    })
    except Exception:
        pass
    return hooks


def discover_adrs() -> list:
    decisions_dir = REPO_ROOT / "decisions"
    adrs = []
    if not decisions_dir.exists():
        return adrs
    for adr_file in sorted(decisions_dir.glob("[0-9]*.md")):
        title = ""
        try:
            for line in adr_file.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
        except Exception:
            pass
        adrs.append({
            "name": adr_file.stem,
            "title": title,
            # Fix A: use .as_posix() so paths are forward-slash on Windows
            "path": adr_file.relative_to(REPO_ROOT).as_posix(),
        })
    return adrs


def discover_edges() -> list:
    """Infer component-reference edges from canonical file bodies (body-grep).

    NOTE (slice #629, ADR-0039 D2): this is a COMPONENT-REFERENCE graph, NOT
    the canonical workflow topology. The authoritative sequential pipeline flow
    lives in the SPEC v2 (pipeline_spec.py) and is exposed via
    ``/api/pipeline`` (rendered by the Architecture topology graph since slice #627).
    This function's output (``/api/architecture`` ``edges``) is consumed only by
    the flat component list section's "Inferred edges" summary — a supplementary
    cross-reference view, not the primary topology.

    Edge types:
      skill -> agent  : skill SKILL.md body mentions a known agent stem name
      agent -> adr    : agent body cites ADR-NNNN or decisions/NNNN-
      hook  -> event  : each hook fires on its declared event

    Conservative: match agent stem names only (not path fragments).
    Deduplicate. Cap at 200 edges with a stderr warning if exceeded.
    """
    edges: list = []
    seen: set = set()

    def add(source: str, stype: str, target: str, ttype: str, label: str = ""):
        key = (source, target)
        if key not in seen:
            seen.add(key)
            edges.append({"source": source, "sourceType": stype,
                          "target": target, "targetType": ttype,
                          "label": label})

    # Collect agent stems for conservative name matching
    agents_dir = REPO_ROOT / ".claude" / "agents"
    agent_stems: set = set()
    if agents_dir.exists():
        for agent_md in agents_dir.glob("*.md"):
            agent_stems.add(agent_md.stem)

    # hook -> event: each configured hook fires on its event (collected first,
    # small set, so they survive if the cap fires)
    settings_path = REPO_ROOT / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            for event, entries in data.get("hooks", {}).items():
                for entry in entries:
                    for hook in entry.get("hooks", []):
                        cmd = hook.get("command", "")
                        m = re.search(r'hooks/([a-z0-9_-]+\.sh)', cmd)
                        hook_id = m.group(1) if m else cmd[:40]
                        add(hook_id, "hook", event, "event", "fires on")
        except Exception:
            pass

    # skill -> agent: skill body mentions an agent stem as a standalone word
    skills_dir = REPO_ROOT / ".claude" / "skills"
    if skills_dir.exists():
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            skill_name = skill_md.parent.name
            try:
                body = skill_md.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for stem in sorted(agent_stems):
                # Word-boundary on stem (hyphenated stems need explicit boundary)
                pattern = r'(?<![a-z0-9-])' + re.escape(stem) + r'(?![a-z0-9-])'
                if re.search(pattern, body):
                    add(skill_name, "skill", stem, "agent", "invokes")

    # agent -> adr: agent body cites ADR-NNNN or decisions/NNNN-
    decisions_dir = REPO_ROOT / "decisions"
    if agents_dir.exists():
        for agent_md in sorted(agents_dir.glob("*.md")):
            stem = agent_md.stem
            try:
                body = agent_md.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            adr_nums: set = set(re.findall(r'ADR-(\d{4})', body))
            adr_nums.update(re.findall(r'decisions/(\d{4})-', body))
            for num in sorted(adr_nums):
                if decisions_dir.exists():
                    matching = list(decisions_dir.glob(f"{num}-*.md"))
                    adr_id = matching[0].stem if matching else f"{num}-unknown"
                else:
                    adr_id = f"{num}-unknown"
                add(stem, "agent", adr_id, "adr", "cites")

    # Cap and log if exceeded (guard against runaway false-positive explosion)
    EDGE_CAP = 200
    if len(edges) > EDGE_CAP:
        print(
            f"[dashboard] WARNING: {len(edges)} edges inferred; capping at {EDGE_CAP}.",
            file=sys.stderr, flush=True,
        )
        edges = edges[:EDGE_CAP]

    return edges


# ---------------------------------------------------------------------------
# Health check helpers (re-implementing DOCS-* and AS-* in Python)
# ---------------------------------------------------------------------------

# SKILL.md paths for parsing check rationale + mechanic text (slice #629).
_AUDIT_META_SKILL = REPO_ROOT / ".claude" / "skills" / "audit-meta" / "SKILL.md"
_AUDIT_SUBAGENTS_SKILL = REPO_ROOT / ".claude" / "skills" / "audit-subagents" / "SKILL.md"

# Mapping: check-id prefix → SKILL.md path.
# DOCS-* and STRUCT-* are defined in audit-meta; AS-* in audit-subagents.
def _skill_md_for_check(check_id: str) -> Path:
    """Return the SKILL.md path that defines the given check ID."""
    if check_id.startswith("AS-") or check_id.startswith("as-"):
        return _AUDIT_SUBAGENTS_SKILL
    # DOCS-* and STRUCT-* both live in audit-meta SKILL.md
    return _AUDIT_META_SKILL


def _parse_skill_rationale(check_id: str) -> tuple:
    """Parse purpose (Rationale) and command (Mechanic) for a check from its SKILL.md.

    Pins the parse to the ``### <check_id> —`` heading (§6 trap) to avoid
    picking up prose mentions of the same ID elsewhere in the file.

    Returns:
        (purpose: str, command: str)
        On no match: purpose = "rationale unavailable — see SKILL.md", command = "".
    """
    skill_path = _skill_md_for_check(check_id)
    try:
        text = skill_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ("rationale unavailable — see SKILL.md", "")

    # Find the heading line: "### <check_id> — ..."
    # Use re.escape so hyphens in IDs (AS-ALL-1) are treated literally.
    heading_pattern = re.compile(
        r'^###\s+' + re.escape(check_id) + r'\s+—',
        re.MULTILINE,
    )
    m = heading_pattern.search(text)
    if not m:
        return ("rationale unavailable — see SKILL.md", "")

    # Slice from the heading to the next "### " heading (or end of file).
    section_start = m.start()
    next_heading = re.search(r'^###\s+', text[m.end():], re.MULTILINE)
    section_end = m.end() + next_heading.start() if next_heading else len(text)
    section = text[section_start:section_end]

    # Extract **Rationale:** block — everything from the marker to the next
    # blank line, "**", or "---" separator.
    rationale_m = re.search(r'\*\*Rationale:\*\*\s*(.+?)(?=\n\n|\n\*\*|\n---|\Z)',
                             section, re.DOTALL)
    purpose = rationale_m.group(1).strip() if rationale_m else "rationale unavailable — see SKILL.md"
    # Collapse any internal newlines to a single space for display brevity.
    purpose = re.sub(r'\s*\n\s*', ' ', purpose).strip()

    # Extract **Mechanic:** block — the literal text / command after the marker.
    # The mechanic may be a single-line inline or a fenced code block.
    mechanic_m = re.search(r'\*\*Mechanic:\*\*\s*(.*?)(?=\n\n\*\*|\n\n###|\n---|\Z)',
                            section, re.DOTALL)
    command = mechanic_m.group(1).strip() if mechanic_m else ""
    # Strip fenced code block markers if present (```...```)
    command = re.sub(r'^```[a-z]*\n?', '', command)
    command = re.sub(r'\n?```$', '', command)
    command = command.strip()

    return (purpose, command)


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _grep_count(pattern: str, text: str, flags=re.MULTILINE) -> int:
    return len(re.findall(pattern, text, flags))


def _grep_fixed(literal: str, text: str) -> bool:
    return literal in text


# -- DOCS checks --

def check_docs1_adr_index_forward() -> dict:
    """DOCS-1: every link in decisions/README.md resolves to an existing file."""
    readme = REPO_ROOT / "decisions" / "README.md"
    if not readme.exists():
        return {"id": "DOCS-1", "result": "FAIL", "detail": "decisions/README.md missing"}
    text = _read_file(readme)
    refs = re.findall(r'\(?([0-9]{4}-[a-z0-9-]+\.md)\)?', text)
    missing = []
    for ref in set(refs):
        if not (REPO_ROOT / "decisions" / ref).exists():
            missing.append(ref)
    if missing:
        return {"id": "DOCS-1", "result": "FAIL", "detail": f"Dangling refs: {missing}"}
    return {"id": "DOCS-1", "result": "PASS", "detail": ""}


def check_docs2_adr_index_reverse() -> dict:
    """DOCS-2: every decisions/NNNN-*.md is in decisions/README.md."""
    readme = REPO_ROOT / "decisions" / "README.md"
    decisions_dir = REPO_ROOT / "decisions"
    if not readme.exists():
        return {"id": "DOCS-2", "result": "FAIL", "detail": "decisions/README.md missing"}
    text = _read_file(readme)
    missing = []
    for f in sorted(decisions_dir.glob("[0-9]*.md")):
        if f.name not in text:
            missing.append(f.name)
    if missing:
        return {"id": "DOCS-2", "result": "FAIL", "detail": f"Not indexed: {missing}"}
    return {"id": "DOCS-2", "result": "PASS", "detail": ""}


def check_docs3_claude_md_agents() -> dict:
    """DOCS-3: every .claude/agents/*.md ref in CLAUDE.md Map exists."""
    claude_md = REPO_ROOT / "CLAUDE.md"
    if not claude_md.exists():
        return {"id": "DOCS-3", "result": "FAIL", "detail": "CLAUDE.md missing"}
    text = _read_file(claude_md)
    refs = re.findall(r'\.claude/agents/([a-z-]+\.md)', text)
    missing = []
    for ref in set(refs):
        if not (REPO_ROOT / ".claude" / "agents" / ref).exists():
            missing.append(ref)
    if missing:
        return {"id": "DOCS-3", "result": "FAIL", "detail": f"Missing agents: {missing}"}
    return {"id": "DOCS-3", "result": "PASS", "detail": ""}


def check_docs4_claude_md_skills() -> dict:
    """DOCS-4: every .claude/skills/*/SKILL.md ref in CLAUDE.md Map exists."""
    claude_md = REPO_ROOT / "CLAUDE.md"
    if not claude_md.exists():
        return {"id": "DOCS-4", "result": "FAIL", "detail": "CLAUDE.md missing"}
    text = _read_file(claude_md)
    refs = re.findall(r'\.claude/skills/([a-z-]+)/SKILL\.md', text)
    missing = []
    for ref in set(refs):
        if not (REPO_ROOT / ".claude" / "skills" / ref / "SKILL.md").exists():
            missing.append(ref)
    if missing:
        return {"id": "DOCS-4", "result": "FAIL", "detail": f"Missing skills: {missing}"}
    return {"id": "DOCS-4", "result": "PASS", "detail": ""}


def check_docs5_n3_literal() -> dict:
    """DOCS-5: no bare N=3 in README.md without adjacent ADR-0013."""
    readme = REPO_ROOT / "README.md"
    if not readme.exists():
        return {"id": "DOCS-5", "result": "PASS", "detail": "README.md missing (skip)"}
    lines = _read_file(readme).splitlines()
    offenders = []
    for i, line in enumerate(lines):
        if "N=3" in line:
            ctx_start = max(0, i - 2)
            ctx_end = min(len(lines), i + 3)
            ctx = "\n".join(lines[ctx_start:ctx_end])
            if "ADR-0013" not in ctx:
                offenders.append(f"L{i+1}: {line.strip()}")
    if offenders:
        return {"id": "DOCS-5", "result": "FAIL", "detail": f"Bare N=3: {offenders}"}
    return {"id": "DOCS-5", "result": "PASS", "detail": ""}


def check_docs6_glossary_md_refs() -> dict:
    """DOCS-6: no GLOSSARY.md refs outside the 2-file allowlist + decisions/."""
    allowlist = {
        ".claude/skills/audit-meta/SKILL.md",
        ".claude/skills/grill-me/SKILL.md",
    }
    offenders = []
    for md_file in REPO_ROOT.rglob("*.md"):
        rel = str(md_file.relative_to(REPO_ROOT)).replace("\\", "/")
        # Skip .git, worktrees, tool-results, decisions/
        if any(skip in rel for skip in [".git/", "worktrees/", "tool-results/", "decisions/"]):
            continue
        if rel in allowlist:
            continue
        try:
            if "GLOSSARY.md" in md_file.read_text(encoding="utf-8", errors="replace"):
                offenders.append(rel)
        except Exception:
            pass
    if offenders:
        return {"id": "DOCS-6", "result": "FAIL", "detail": f"GLOSSARY.md refs: {offenders}"}
    return {"id": "DOCS-6", "result": "PASS", "detail": ""}


def check_docs7_adr_citations() -> dict:
    """DOCS-7: every [ADR-NNNN](decisions/NNNN-*.md) citation resolves."""
    fake_slugs = re.compile(
        r'decisions/00\d{2}-(old-name|fictional|fictional-adr|new-adr|new-decision)\.md'
    )
    offenders = []
    for md_file in REPO_ROOT.rglob("*.md"):
        rel = str(md_file.relative_to(REPO_ROOT)).replace("\\", "/")
        if ".git/" in rel or "worktrees/" in rel:
            continue
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for target in re.findall(r'decisions/[0-9]{4}-[a-z0-9-]+\.md', text):
            if fake_slugs.match(target):
                continue
            if not (REPO_ROOT / target).exists():
                offenders.append(f"{rel} -> {target}")
    if offenders:
        return {"id": "DOCS-7", "result": "FAIL", "detail": f"Dangling ADR citations: {offenders[:5]}"}
    return {"id": "DOCS-7", "result": "PASS", "detail": ""}


def check_docs8_supersession_notes() -> dict:
    """DOCS-8 (WARN): decisions/README.md Status column has superseded-by annotations (per-pair)."""
    readme = REPO_ROOT / "decisions" / "README.md"
    if not readme.exists():
        return {"id": "DOCS-8", "result": "WARN", "detail": "decisions/README.md missing"}
    readme_lines = _read_file(readme).splitlines()
    missing_annotations = []
    decisions_dir = REPO_ROOT / "decisions"
    # Per-pair mechanic: enumerate each `- **Supersedes:**` declaration across decisions/*.md,
    # extract the superseded ADR number, and check that the superseded ADR's row in
    # decisions/README.md carries a "superseded by" annotation.
    for adr_file in sorted(decisions_dir.glob("[0-9]*.md")):
        try:
            adr_text = _read_file(adr_file)
            for match in re.finditer(r'^- \*\*Supersedes:\*\*\s*(.+)$', adr_text, re.MULTILINE):
                superseded_ref = match.group(1).strip()
                # Extract superseded ADR numbers (e.g. "ADR-0001" or bare "D9 in ADR-0001")
                superseded_ids = re.findall(r'ADR-(\d{4})', superseded_ref)
                if not superseded_ids:
                    # Also match bare "0001"-style references
                    superseded_ids = re.findall(r'\b(\d{4})\b', superseded_ref)
                for sid in superseded_ids:
                    # Find the table row in decisions/README.md for the superseded ADR.
                    # Table rows start with '|' and contain the ADR slug pattern.
                    row_found = False
                    row_has_annotation = False
                    for line in readme_lines:
                        if line.startswith("|") and f"({sid}-" in line:
                            row_found = True
                            if "superseded by" in line.lower():
                                row_has_annotation = True
                            break
                    if row_found and not row_has_annotation:
                        missing_annotations.append(
                            f"{adr_file.name} supersedes ADR-{sid}: missing 'superseded by' in README row"
                        )
        except Exception:
            pass
    if missing_annotations:
        return {"id": "DOCS-8", "result": "WARN", "detail": f"Missing annotations: {missing_annotations[:3]}"}
    return {"id": "DOCS-8", "result": "PASS", "detail": ""}


def check_docs9_glossary_cap() -> dict:
    """DOCS-9 (WARN): CLAUDE.md glossary entry count <= 35."""
    claude_md = REPO_ROOT / "CLAUDE.md"
    if not claude_md.exists():
        return {"id": "DOCS-9", "result": "WARN", "detail": "CLAUDE.md missing"}
    text = _read_file(claude_md)
    lines = text.splitlines()
    in_glossary = False
    count = 0
    for line in lines:
        if re.match(r'^## Glossary', line):
            in_glossary = True
            continue
        if in_glossary and re.match(r'^## ', line):
            break
        if in_glossary and re.match(r'^- \*\*', line):
            count += 1
    if count > 35:
        return {"id": "DOCS-9", "result": "WARN", "detail": f"Glossary has {count} entries (cap 35)"}
    return {"id": "DOCS-9", "result": "PASS", "detail": f"{count} entries"}


def check_docs10_backlog_surfacing() -> dict:
    """DOCS-10: no backlog-label surfacing idiom in agents/skills (except allowlist)."""
    allowlist = {"backlog-critic.md", "promote-to-backlog", "audit-meta/SKILL.md", "audit-subagents/SKILL.md"}
    pattern = re.compile(r'(`backlog`-labeled|--label backlog)')
    offenders = []
    for search_dir in [REPO_ROOT / ".claude" / "agents", REPO_ROOT / ".claude" / "skills"]:
        if not search_dir.exists():
            continue
        for md_file in search_dir.rglob("*.md"):
            rel = str(md_file.relative_to(REPO_ROOT)).replace("\\", "/")
            if any(skip in rel for skip in allowlist):
                continue
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
                if pattern.search(text):
                    offenders.append(rel)
            except Exception:
                pass
    if offenders:
        return {"id": "DOCS-10", "result": "FAIL", "detail": f"Backlog-label drift: {offenders}"}
    return {"id": "DOCS-10", "result": "PASS", "detail": ""}


# -- AS-* checks --

def _check_as_all_1(path: Path) -> dict:
    """AS-ALL-1: frontmatter name/description/tools/model."""
    text = _read_file(path)
    count = len(re.findall(r'^(name|description|tools|model):', text, re.MULTILINE))
    result = "PASS" if count >= 4 else "FAIL"
    return {"id": "AS-ALL-1", "result": result, "detail": f"field count={count}"}


def _check_as_all_2(path: Path) -> dict:
    """AS-ALL-2: Tool boundaries section heading."""
    text = _read_file(path)
    ok = bool(re.search(r'^#+\s*Tool boundaries', text, re.MULTILINE))
    return {"id": "AS-ALL-2", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_all_3(path: Path) -> dict:
    """AS-ALL-3: cross-reference section heading."""
    text = _read_file(path)
    ok = bool(re.search(r'^#+\s*.*(References|Related|See also|Cross-refs)', text,
                        re.MULTILINE | re.IGNORECASE))
    return {"id": "AS-ALL-3", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_all_4(path: Path) -> dict:
    """AS-ALL-4: no backlog-label surfacing idiom (backlog-critic excluded)."""
    if path.name == "backlog-critic.md":
        return {"id": "AS-ALL-4", "result": "N/A", "detail": "excluded"}
    text = _read_file(path)
    has_drift = bool(re.search(r'(`backlog`-labeled|--label backlog)', text))
    return {"id": "AS-ALL-4", "result": "FAIL" if has_drift else "PASS", "detail": ""}


def _check_as_all_5(path: Path) -> dict:
    """AS-ALL-5: Mandatory reading order OR When invoked section."""
    text = _read_file(path)
    ok = bool(re.search(r'^#+\s*(Mandatory reading order|When invoked)', text, re.MULTILINE))
    return {"id": "AS-ALL-5", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_crit_1(path: Path) -> dict:
    """AS-CRIT-1: Default conservative literal."""
    ok = "Default conservative" in _read_file(path)
    return {"id": "AS-CRIT-1", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_crit_2(path: Path) -> dict:
    """AS-CRIT-2: paranoid OR Adversarial mindset (backlog-critic excluded)."""
    if path.name == "backlog-critic.md":
        return {"id": "AS-CRIT-2", "result": "N/A", "detail": "excluded"}
    text = _read_file(path)
    ok = bool(re.search(r'(paranoid|Adversarial mindset)', text))
    return {"id": "AS-CRIT-2", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_crit_3(path: Path) -> dict:
    """AS-CRIT-3: VERDICT: REASON: ROUND: in body."""
    text = _read_file(path)
    ok = "VERDICT:" in text and "REASON:" in text and "ROUND:" in text
    return {"id": "AS-CRIT-3", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_crit_4(path: Path) -> dict:
    """AS-CRIT-4: documentation-contract check.

    Verifies the critic documents its verdict-body output contract by delegation:
    (a) an Output-format section heading is present AND
    (b) an ADR-0005 citation is present.
    Both required; any absent → FAIL.
    """
    text = _read_file(path)
    has_output_format = bool(re.search(r'^#+\s*Output format', text, re.MULTILINE))
    has_adr0005 = "ADR-0005" in text
    ok = has_output_format and has_adr0005
    missing = []
    if not has_output_format:
        missing.append("Output format heading")
    if not has_adr0005:
        missing.append("ADR-0005 citation")
    return {"id": "AS-CRIT-4", "result": "PASS" if ok else "FAIL",
            "detail": "" if ok else f"missing: {', '.join(missing)}"}


def _check_as_gen_1(path: Path) -> dict:
    """AS-GEN-1: RESULT: REASON: ARTIFACTS: in generator body."""
    text = _read_file(path)
    ok = "RESULT:" in text and "REASON:" in text and "ARTIFACTS:" in text
    return {"id": "AS-GEN-1", "result": "PASS" if ok else "FAIL", "detail": ""}


def _is_critic(stem: str, path: Path) -> bool:
    return stem in KNOWN_CRITICS or stem == "reviewer" or stem.endswith("-critic")


def _enrich_checks(checks: list) -> list:
    """Add purpose + command fields to each check dict from the SKILL.md (slice #629).

    Mutates each dict in-place and returns the list for convenience.
    purpose / command are sourced from the SKILL.md rationale/mechanic blocks
    so CHECK 9 stays green (no hand-authored copies in dashboard source).
    """
    for c in checks:
        check_id = c.get("id", "")
        if check_id:
            purpose, command = _parse_skill_rationale(check_id)
        else:
            purpose, command = ("rationale unavailable — see SKILL.md", "")
        c["purpose"] = purpose
        c["command"] = command
    return checks


def audit_subagents() -> dict:
    agents_dir = REPO_ROOT / ".claude" / "agents"
    results = {}
    if not agents_dir.exists():
        return results
    for agent_md in sorted(agents_dir.glob("*.md")):
        stem = agent_md.stem
        is_critic = _is_critic(stem, agent_md)
        checks = [
            _check_as_all_1(agent_md),
            _check_as_all_2(agent_md),
            _check_as_all_3(agent_md),
            _check_as_all_4(agent_md),
            _check_as_all_5(agent_md),
        ]
        if is_critic:
            checks += [
                _check_as_crit_1(agent_md),
                _check_as_crit_2(agent_md),
                _check_as_crit_3(agent_md),
                _check_as_crit_4(agent_md),
            ]
        else:
            checks.append(_check_as_gen_1(agent_md))
        results[stem] = {
            "type": "critic" if is_critic else "generator",
            "checks": _enrich_checks(checks),
        }
    return results


def audit_meta() -> dict:
    checks = [
        check_docs1_adr_index_forward(),
        check_docs2_adr_index_reverse(),
        check_docs3_claude_md_agents(),
        check_docs4_claude_md_skills(),
        check_docs5_n3_literal(),
        check_docs6_glossary_md_refs(),
        check_docs7_adr_citations(),
        check_docs8_supersession_notes(),
        check_docs9_glossary_cap(),
        check_docs10_backlog_surfacing(),
    ]
    return {"checks": _enrich_checks(checks)}


def cascade_finder_summary() -> dict:
    cascade_script = REPO_ROOT / "tools" / "cascade-finder.py"
    if not cascade_script.exists():
        return {"available": False, "detail": "tools/cascade-finder.py not found"}
    try:
        result = subprocess.run(
            [sys.executable, str(cascade_script), "--help"],
            capture_output=True, text=True, timeout=10, cwd=str(REPO_ROOT),
        )
        return {"available": True, "detail": "cascade-finder.py present; use /api/architecture edges for data"}
    except Exception as e:
        return {"available": False, "detail": str(e)}


# ---------------------------------------------------------------------------
# Tail-seek helper — yields lines from a text file in reverse order.
# Reads in 64 KiB chunks from the end; never loads the whole file.
# ---------------------------------------------------------------------------

def _iter_lines_reversed(path: Path, chunk_size: int = 65536):
    """Yield UTF-8 decoded lines from *path* in reverse order (last line first).

    Uses seek/read on 64 KiB chunks so callers can stop early after collecting
    enough session groups without ever loading the full file into memory.
    """
    with path.open("rb") as f:
        f.seek(0, 2)  # seek to end
        remaining = f.tell()
        buf = b""
        while remaining > 0:
            read_size = min(chunk_size, remaining)
            remaining -= read_size
            f.seek(remaining)
            chunk = f.read(read_size)
            # Prepend new chunk to leftover buffer
            buf = chunk + buf
            # Split on newlines; keep first fragment (may be incomplete line)
            # The last element of split is the incomplete leading fragment
            parts = buf.split(b"\n")
            # parts[0] may be partial; save it; yield the rest in reverse
            buf = parts[0]
            for part in reversed(parts[1:]):
                decoded = part.decode("utf-8", errors="replace")
                yield decoded
        # Yield whatever is left in buf (the very first line of the file)
        if buf:
            yield buf.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Work-items: PRD→slice→PR tree via gh CLI (GET /api/workitems)
# ---------------------------------------------------------------------------

# In-process cache: {"data": {...}, "ts": float}
_workitems_cache: dict = {}
_WORKITEMS_TTL = 30  # seconds


def _gh_list(args: list, timeout: int = 10) -> list:
    """Run a gh CLI command and return parsed JSON list.

    On any error (timeout, missing binary, non-zero exit, bad JSON) returns [].
    Never raises.
    """
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO_ROOT),
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            return []
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return []
    except FileNotFoundError:
        return []
    except Exception:
        return []


def fetch_workitems() -> dict:
    """Return PRD→slice→PR tree + deferred captures, 30s in-process cache.

    Response shape:
      { prd: [...], slices: [...], prs: [...], captures: [...], backlog: [...] }

    Each item includes createdAt so the client can flag stale slices (>7 days).
    captures = gh issue list --label captured --state open --limit 20
    backlog  = gh issue list --label backlog  --state open --limit 20

    On any failure, returns {} (never raises, never hangs the dashboard).
    """
    import time

    now = time.time()
    cached = _workitems_cache.get("data")
    if cached is not None and (now - _workitems_cache.get("ts", 0)) < _WORKITEMS_TTL:
        return cached

    try:
        prds = _gh_list([
            "issue", "list",
            "--label", "prd",
            "--state", "all",
            "--limit", "30",
            "--json", "number,title,state,labels,createdAt",
        ])
        slices = _gh_list([
            "issue", "list",
            "--label", "slice",
            "--state", "all",
            "--limit", "60",
            "--json", "number,title,state,labels,createdAt",
        ])
        prs = _gh_list([
            "pr", "list",
            "--state", "all",
            "--limit", "30",
            "--json", "number,title,state,labels,createdAt",
        ])
        # Deferred captures: raw captured tier + curated backlog tier.
        # Both use the same bounded helper (timeout=10, soft-degrade → []).
        captures = _gh_list([
            "issue", "list",
            "--label", "captured",
            "--state", "open",
            "--limit", "20",
            "--json", "number,title,labels,createdAt",
        ])
        backlog = _gh_list([
            "issue", "list",
            "--label", "backlog",
            "--state", "open",
            "--limit", "20",
            "--json", "number,title,labels,createdAt",
        ])

        # Since _gh_list never raises, an all-empty result when no data exists is fine.
        data = {
            "prd": prds,
            "slices": slices,
            "prs": prs,
            "captures": captures,
            "backlog": backlog,
        }

        _workitems_cache["data"] = data
        _workitems_cache["ts"] = now
        return data
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class DashboardHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):  # quiet by default; override for debug
        pass

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, body: bytes, content_type: str = "text/html; charset=utf-8",
                   status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str):
        self._send_json({"error": message}, status)

    # Reader-side fixture-pattern guard — mirrors the writer's FIXTURE_PATTERN in
    # log-tool-event.sh so the server defensively drops synthetic sids even if the
    # writer's routing was bypassed (e.g. direct file writes during testing).
    _FIXTURE_SID_RE = re.compile(
        r"^(demo|test|verify|fixture|manual|sess-)", re.IGNORECASE
    )

    @classmethod
    def _is_valid_v2_event(cls, obj: dict) -> bool:
        """Return True iff obj is a schema-v2 event with a non-empty, non-fixture session_id."""
        if obj.get("v") != 2:
            return False
        sid = obj.get("session_id", "")
        if not sid:
            return False
        if cls._FIXTURE_SID_RE.match(sid):
            return False
        return True

    def _serve_runs(self, query: dict) -> dict:
        """Return run metadata or a single session's events — tail-seek, no full-file read.

        Query params:
          n / limit : int  — how many runs to return (default 2); metadata-only
          before    : str  — session_id cursor; return runs BEFORE it (metadata-only)
          session   : str  — return ONE session's full events as {run:{...events:[]}}

        Metadata response: {runs: [...], rejected_lines: N}
          rejected_lines counts invalid/legacy/fixture lines encountered during the scan
          (not silently discarded — surfaced for transparency per slice #671).
        Single-session response: {run: {session_id, first_ts, last_ts, events: []}}

        Validation: only schema-v2 events (``"v":2``) with a non-empty, non-fixture
        session_id are accepted.  Legacy v1 lines, malformed JSON, empty lines, and
        fixture-pattern session_ids are counted in ``rejected_lines`` and dropped.

        Runs are ordered newest-first (by first_ts descending).
        Events within a run are time-ordered (ascending, as logged).

        Implementation: reads the file backwards in 64 KiB chunks to collect
        only the lines needed for the last N session_id groups.  For the
        ?before cursor it scans backward from the end to skip sessions until
        the cursor session_id is exhausted, then collects N more groups.
        This avoids loading the full file on the hot path.
        """
        log_path = REPO_ROOT / ".claude" / "logs" / "workflow-events.jsonl"
        if not log_path.exists():
            # Return appropriate empty shape depending on query mode
            if (query.get("session") or [""])[0]:
                return {"run": None}
            return {"runs": [], "rejected_lines": 0}

        # --- ?session=<id> branch: return ONE session's full events ---
        session_id_filter = (query.get("session") or [""])[0]
        if session_id_filter:
            try:
                lines_reversed = _iter_lines_reversed(log_path)
                events_reversed: list = []
                sid_seen = False
                for raw in lines_reversed:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw)
                    except Exception:
                        continue
                    if not self._is_valid_v2_event(obj):
                        continue
                    sid = obj.get("session_id", "")
                    if sid == session_id_filter:
                        sid_seen = True
                        events_reversed.append(obj)
                    elif sid_seen:
                        # We've moved past the target session (reading reversed)
                        break
                events = list(reversed(events_reversed))
                if not events:
                    return {"run": None}
                return {"run": {
                    "session_id": session_id_filter,
                    "first_ts": events[0].get("ts", ""),
                    "last_ts": events[-1].get("ts", ""),
                    "events": events,
                }}
            except Exception:
                return {"run": None}

        # --- Default: metadata-only for ?n=N / ?before= ---
        try:
            n = int((query.get("n") or query.get("limit") or ["2"])[0])
        except (ValueError, IndexError, TypeError):
            n = 2
        n = max(1, min(n, 50))  # safety clamp

        before_cursor = None
        before_raw = (query.get("before") or [""])[0]
        if before_raw:
            before_cursor = before_raw

        rejected_lines = 0

        try:
            # Read lines backward via chunk-seek so we never load the full file
            lines_reversed = _iter_lines_reversed(log_path)

            # Collect session groups in reverse insertion order (newest first).
            # We only track metadata (first_ts, last_ts, event_count) — no events list.
            sessions_newest_first: list = []  # list of (sid, first_ts, last_ts, count)
            sid_to_idx: dict = {}

            # When before_cursor is set we skip all sessions that appear AFTER
            # the cursor in the file (i.e., sessions newer than the cursor when
            # reading reversed).  We track whether we have SEEN the cursor
            # session at all; only AFTER we first encounter it AND then move past
            # it (into a different session_id) do we start collecting.
            cursor_seen = False  # have we observed at least one cursor-session line?
            in_before_skip = (before_cursor is not None)

            for raw in lines_reversed:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    rejected_lines += 1
                    continue

                # Schema-v2 validation: reject legacy/invalid/fixture lines.
                if not self._is_valid_v2_event(obj):
                    rejected_lines += 1
                    continue

                sid = obj.get("session_id", "")

                if in_before_skip:
                    if sid == before_cursor:
                        # Inside the cursor session — mark it seen, keep skipping
                        cursor_seen = True
                        continue
                    elif not cursor_seen:
                        # Haven't seen the cursor yet; this is a newer session — skip
                        continue
                    else:
                        # cursor_seen and now a different sid → we've passed the cursor
                        in_before_skip = False
                        # Fall through to process this line normally

                ts = obj.get("ts", "")
                if sid not in sid_to_idx:
                    if len(sessions_newest_first) >= n:
                        break  # have enough sessions; stop reading
                    sid_to_idx[sid] = len(sessions_newest_first)
                    # (sid, first_ts_placeholder, last_ts, count)
                    # Reading reversed: first line we see is the LAST event
                    sessions_newest_first.append([sid, ts, ts, 1])
                else:
                    idx = sid_to_idx[sid]
                    entry = sessions_newest_first[idx]
                    # Reading reversed: ts of each subsequent line is EARLIER
                    # → update first_ts to this (earlier) timestamp
                    entry[1] = ts  # first_ts moves backward as we read
                    entry[3] += 1  # increment count

        except Exception:
            return {"runs": [], "rejected_lines": rejected_lines}

        runs = []
        for sid, first_ts, last_ts, event_count in sessions_newest_first:
            runs.append({"session_id": sid, "first_ts": first_ts,
                         "last_ts": last_ts, "event_count": event_count})

        # Already newest-first from reversed iteration; sort is belt-and-suspenders
        runs.sort(key=lambda r: r["first_ts"], reverse=True)
        return {"runs": runs, "rejected_lines": rejected_lines}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            index = DASHBOARD_DIR / "index.html"
            if index.exists():
                self._send_text(index.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send_error(404, "index.html not found")

        elif path == "/api/architecture":
            data = {
                "skills": discover_skills(),
                "agents": discover_agents(),
                "hooks": discover_hooks(),
                "adrs": discover_adrs(),
                "edges": discover_edges(),
            }
            self._send_json(data)

        elif path == "/api/pipeline":
            # Canonical topology spec (ADR-0053 D2 / ADR-0039 D1 extended).
            # Returns SPEC v2 from pipeline_spec.py; dashboard index.html fetches
            # this for the declared topology render.
            self._send_json(_get_pipeline_spec())

        elif path == "/api/health":
            data = {
                "auditMeta": audit_meta(),
                "auditSubagents": audit_subagents(),
                "cascadeFinder": cascade_finder_summary(),
            }
            self._send_json(data)

        elif path == "/api/workitems":
            self._send_json(fetch_workitems())

        elif path == "/api/live-progress":
            # GET /api/live-progress — Lane A run-progress for most recent open PRD.
            # Stale-while-revalidate: if a previous payload exists, ALWAYS return it
            # immediately (with "refreshing":true while a rebuild is in flight).
            # {"status":"computing"} is returned ONLY when no payload has ever been
            # built since process start.  Pattern mirrors /api/rollup.
            global _live_progress_computing
            with _live_progress_lock:
                cached = _live_progress_cache.get("data")
                now = time.time()
                ts = _live_progress_cache.get("ts", 0)
                expired = (now - ts) >= _LIVE_PROGRESS_TTL
                if cached is not None and not expired:
                    # Fresh cache — return as-is
                    self._send_json(cached)
                    return
                if cached is not None and expired:
                    # Stale-while-revalidate: serve stale payload immediately,
                    # kick off a background refresh if not already running.
                    payload = dict(cached)
                    payload["refreshing"] = True
                    if not _live_progress_computing:
                        _live_progress_computing = True
                        t = threading.Thread(
                            target=_live_progress_background, daemon=True
                        )
                        t.start()
                    self._send_json(payload)
                    return
                # No payload ever built yet — bootstrap case
                if _live_progress_computing:
                    self._send_json({"status": "computing"})
                    return
                _live_progress_computing = True
            t = threading.Thread(
                target=_live_progress_background, daemon=True
            )
            t.start()
            self._send_json({"status": "computing"})

        elif path == "/api/runs":
            self._send_json(self._serve_runs(query))

        elif path == "/api/live-poll":
            # GET /api/live-poll?cursor=<N>
            # Byte-cursor incremental read of workflow-events.jsonl (Lane B).
            # Returns {cursor, events[], reset}.
            cursor_raw = (query.get("cursor") or ["0"])[0]
            self._send_json(serve_live_poll(cursor_raw))

        elif path == "/api/trail":
            # GET /api/trail?prd=N — raw artifact trail for a PRD (ADR-0053 D1/D4).
            prd_raw = query.get("prd", [""])[0]
            if not prd_raw or not prd_raw.isdigit():
                self._send_error(400, "prd parameter required (integer)")
                return
            try:
                trail = get_trail(int(prd_raw))
                self._send_json(trail)
            except Exception as e:
                self._send_error(500, str(e))

        elif path == "/api/comparison":
            # GET /api/comparison?prd=N[&format=download] — comparison report (ADR-0053 D3).
            # ?format=download serves identical JSON with Content-Disposition attachment.
            prd_raw = query.get("prd", [""])[0]
            if not prd_raw or not prd_raw.isdigit():
                self._send_error(400, "prd parameter required (integer)")
                return
            fmt = query.get("format", [""])[0]
            try:
                trail = get_trail(int(prd_raw))
                spec = get_spec_for_compare()
                report = compare(spec, trail)
                if fmt == "download":
                    import json as _json
                    body = _json.dumps(report, indent=2).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header(
                        "Content-Disposition",
                        f'attachment; filename="prd-{prd_raw}-comparison.json"',
                    )
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self._send_json(report)
            except Exception as e:
                self._send_error(500, str(e))

        elif path == "/api/trail-runs":
            # GET /api/trail-runs?last=N — list of last N closed PRDs for run picker.
            last_raw = query.get("last", ["20"])[0]
            try:
                last_n = int(last_raw) if last_raw.isdigit() else 20
            except (ValueError, AttributeError):
                last_n = 20
            try:
                numbers = get_closed_prd_numbers(last_n=last_n)
                # Fetch minimal metadata (title + closedAt) for each PRD
                runs = []
                for n in numbers:
                    trail = get_trail(n)
                    runs.append({
                        "number": n,
                        "title": trail.get("prd_title", f"PRD #{n}"),
                        "closed_at": trail.get("prd_closed_at", ""),
                        "wall_time_s": trail.get("wall_time_s"),
                    })
                self._send_json({"runs": runs})
            except Exception as e:
                self._send_error(500, str(e))

        elif path == "/api/rollup":
            # GET /api/rollup?last=N — repo rollup over last N closed PRDs.
            # Returns immediately: {"status":"computing"} while background thread
            # runs; client polls every 2s until status is absent (data ready).
            last_raw = query.get("last", ["10"])[0]
            try:
                last_n = int(last_raw) if last_raw.isdigit() else 10
            except (ValueError, AttributeError):
                last_n = 10
            with _rollup_lock:
                cached = _rollup_cache.get(last_n)
                now = time.time()
                if cached and (now - cached.get("ts", 0)) < _ROLLUP_CACHE_TTL:
                    # Serve cached result; propagate any error status from failed run
                    self._send_json(cached["data"])
                    return
                if _rollup_computing.get(last_n):
                    # Already in flight — return computing sentinel
                    self._send_json({"status": "computing", "last_n": last_n})
                    return
                # Kick off background computation
                _rollup_computing[last_n] = True
            t = threading.Thread(
                target=_rollup_background, args=(last_n,), daemon=True
            )
            t.start()
            self._send_json({"status": "computing", "last_n": last_n})

        elif path == "/api/file":
            rel_path = query.get("path", [""])[0]
            if not rel_path:
                self._send_error(400, "path parameter required")
                return
            # Fix A: normalize any incoming backslashes (Windows round-trip defence)
            rel_path = rel_path.replace("\\", "/")
            # Path-traversal protection: resolve against repo root
            try:
                target = (REPO_ROOT / rel_path).resolve()
                if not target.is_relative_to(REPO_ROOT):
                    self._send_error(403, "Path traversal rejected")
                    return
                if not target.exists() or not target.is_file():
                    self._send_error(404, "File not found")
                    return
                content = target.read_text(encoding="utf-8", errors="replace")
                self._send_json({"path": rel_path, "content": content})
            except Exception as e:
                self._send_error(400, str(e))

        else:
            self._send_error(404, f"Not found: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    port = int(os.environ.get("DASH_PORT", "8765"))
    server = ThreadingHTTPServer(("localhost", port), DashboardHandler)
    server.daemon_threads = True
    print(f"Dashboard running at http://localhost:{port}", flush=True)
    print(f"Repo root: {REPO_ROOT}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    if not os.environ.get("DASH_NO_BROWSER"):
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception as e:
            print(f"(could not open browser: {e})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.", flush=True)
        server.server_close()


# ---------------------------------------------------------------------------
# README generator  (--generate-readme CLI mode)
# ---------------------------------------------------------------------------

# render_pipeline_mermaid: generates a mermaid flowchart TD from the SPEC v2
# (pipeline_spec.py, ADR-0053 D2 / ADR-0039 D1 extended).  Both the README
# diagram and the dashboard topology are sourced from the same SPEC.
#
# The generated diagram preserves the visual shape of the previous diagram:
#   S1 idea-capture → S2 PRD+slice → S3 implementation → S4 acceptance
#   SS side-workflows in a secondary lane.
# Solid edges = required:always; dashed edges = conditional / unmeasurable.

def _node_id(name: str) -> str:
    """Sanitise a SPEC node id to a valid mermaid node ID (hyphens → underscores)."""
    return name.replace("-", "_")


def _node_decl_spec(name: str, kind: str, label: str) -> str:
    """Return a mermaid node declaration for a SPEC v2 node.

    Shape conventions (matching vis-network topology render):
      human        — [label]      (rectangle)
      orchestrator — ["/name"]    (rectangle, slash-prefix)
      skill        — ["/name"]    (rectangle, slash-prefix)
      agent (critic)   — {name}   (rhombus)
      agent (generator)— [name]   (rectangle)
      artifact     — [(label)]    (cylinder-ish via (()) not available; use [()])
    """
    nid = _node_id(name)
    if kind == "human":
        return f"{nid}[\"{label}\"]"
    elif kind in ("skill", "orchestrator"):
        return f"{nid}[\"/{name}\"]"
    elif kind == "artifact":
        return f"{nid}[({label})]"
    elif kind == "agent":
        # Distinguish critics from generators by name heuristic
        if name.endswith("-critic") or name in ("reviewer",):
            return f"{nid}{{{{{label}}}}}"
        return f"{nid}[{label}]"
    else:
        return f"{nid}[{label}]"


def _edge_line_spec(edge: dict) -> str:
    """Render one SPEC edge to a mermaid edge string.

    Uses from_node/to_node (hyphen ids) converted to underscores for mermaid.
    style='dashed' → -.-  or  -.label.-
    style='solid'  → -->  or  -->|label|
    """
    src = _node_id(edge["from_node"])
    tgt = _node_id(edge["to_node"])
    label = (edge.get("label") or "").strip()
    style = edge.get("style", "solid")

    if style == "dashed":
        if label:
            return f"  {src} -.{label}.- {tgt}"
        else:
            return f"  {src} -.- {tgt}"
    else:  # solid
        if label:
            return f"  {src} -->|{label}| {tgt}"
        else:
            return f"  {src} --> {tgt}"


def render_pipeline_mermaid(spec: dict) -> str:
    """Render the SPEC v2 to a mermaid flowchart TD string.

    Returns a complete ```mermaid ... ``` fenced block for embedding in
    README.md via the {{GENERATED:pipeline-diagram}} placeholder.

    Derives ALL structure from spec (ADR-0053 D2):
    - Node declarations from spec['nodes'] grouped by stage field.
    - Edges from spec['edges'] (from_node/to_node in hyphen id-space).
    - ClassDef assignments from each node's kind field.

    Node IDs are sanitised (hyphens → underscores); labels from SPEC.
    """
    nodes = spec.get("nodes", {})
    edges = spec.get("edges", [])

    # Group nodes by stage
    by_stage: dict = {}
    for name, meta in nodes.items():
        stage = meta.get("stage")
        if stage not in by_stage:
            by_stage[stage] = []
        by_stage[stage].append((name, meta))

    # Collect node_id → mermaid class for classDef assignments
    node_classes: dict[str, str] = {}
    for name, meta in nodes.items():
        kind = meta.get("kind", "agent")
        nid = _node_id(name)
        if name == "reviewer":
            node_classes[nid] = "reviewer_cls"
        elif kind == "human":
            node_classes[nid] = "human"
        elif kind in ("skill", "orchestrator"):
            node_classes[nid] = "skill"
        elif kind == "agent":
            if name.endswith("-critic") or name == "reviewer":
                node_classes[nid] = "critic"
            else:
                node_classes[nid] = "gen"
        elif kind == "artifact":
            node_classes[nid] = "artifact"

    lines: list[str] = []
    lines.append("```mermaid")
    lines.append("flowchart TD")

    # ---- Subgraph S1: Idea capture -----------------------------------------
    lines.append('  subgraph S1["Stage 1: Idea capture"]')
    for name, meta in by_stage.get("S1", []):
        lines.append(f"    {_node_decl_spec(name, meta['kind'], meta['label'])}")
    lines.append("  end")

    # ---- Subgraph S2: PRD authoring + slice decomposition ------------------
    lines.append('  subgraph S2["Stage 2-3: PRD + slice decomposition"]')
    for name, meta in by_stage.get("S2", []):
        lines.append(f"    {_node_decl_spec(name, meta['kind'], meta['label'])}")
    lines.append("  end")

    # ---- Subgraph S3: Implementation ---------------------------------------
    lines.append('  subgraph S3["Stage 4: Implementation"]')
    for name, meta in by_stage.get("S3", []):
        lines.append(f"    {_node_decl_spec(name, meta['kind'], meta['label'])}")
    lines.append("  end")

    # ---- Subgraph S4: Acceptance -------------------------------------------
    lines.append('  subgraph S4["Stage 5: Acceptance"]')
    for name, meta in by_stage.get("S4", []):
        lines.append(f"    {_node_decl_spec(name, meta['kind'], meta['label'])}")
    lines.append("  end")

    # ---- Subgraph SS: Side workflows ----------------------------------------
    lines.append('  subgraph SS["Side workflows"]')
    for name, meta in by_stage.get("SS", []):
        lines.append(f"    {_node_decl_spec(name, meta['kind'], meta['label'])}")
    lines.append("  end")

    # ---- Edges (from SPEC edges list) ----------------------------------------
    for edge in edges:
        lines.append(_edge_line_spec(edge))

    # ---- classDef declarations -----------------------------------------------
    lines.append("  classDef human fill:#3b82f6,color:#fff")
    lines.append("  classDef skill fill:#14b8a6,color:#fff")
    lines.append("  classDef gen fill:#22c55e,color:#fff")
    lines.append("  classDef critic fill:#f97316,color:#fff")
    lines.append("  classDef reviewer_cls fill:#ef4444,color:#fff")
    lines.append("  classDef artifact fill:#9ca3af,color:#fff")

    # ---- class assignments from kind/name ----------------------------------
    by_class: dict[str, list[str]] = {}
    for nid, cls in node_classes.items():
        by_class.setdefault(cls, []).append(nid)
    for cls_name in ("human", "skill", "gen", "critic", "reviewer_cls", "artifact"):
        if cls_name in by_class:
            ids = ",".join(sorted(by_class[cls_name]))
            lines.append(f"  class {ids} {cls_name}")

    lines.append("```")
    return "\n".join(lines)


def _build_component_map() -> str:
    """Build the component-map section from filesystem discovery."""
    skills = discover_skills()
    agents = discover_agents()
    hooks = discover_hooks()
    adrs = discover_adrs()

    lines = []

    # Skills
    lines.append("### Skills\n")
    lines.append("User-invocable commands under `.claude/skills/`:\n")
    if skills:
        for s in skills:
            name = s.get("name") or s["path"].split("/")[-2]
            desc = s.get("description", "")
            path = s["path"]
            if desc:
                lines.append(f"- **[`/{name}`]({path})** — {desc}")
            else:
                lines.append(f"- **[`/{name}`]({path})**")
    else:
        lines.append("_(no skills found)_")
    lines.append("")

    # Agents
    lines.append("### Subagents\n")
    lines.append("Specialist agents under `.claude/agents/`:\n")
    critics = [a for a in agents if a.get("type") == "critic"]
    generators = [a for a in agents if a.get("type") != "critic"]
    if critics:
        lines.append("**Critics** (adversarial gates):\n")
        for a in critics:
            name = a.get("name") or a["stem"]
            desc = a.get("description", "")
            path = a["path"]
            if desc:
                lines.append(f"- **[`{name}`]({path})** — {desc}")
            else:
                lines.append(f"- **[`{name}`]({path})**")
        lines.append("")
    if generators:
        lines.append("**Generators** (output-producing agents):\n")
        for a in generators:
            name = a.get("name") or a["stem"]
            desc = a.get("description", "")
            path = a["path"]
            if desc:
                lines.append(f"- **[`{name}`]({path})** — {desc}")
            else:
                lines.append(f"- **[`{name}`]({path})**")
        lines.append("")

    # Hooks
    lines.append("### Hooks\n")
    lines.append(
        "Claude Code session hooks configured in `.claude/settings.json`"
        " (scripts in `.claude/hooks/`):\n"
    )
    if hooks:
        seen_hooks = set()
        for h in hooks:
            key = (h.get("clean_name", h["name"]), h["event"], h.get("matcher", ""))
            if key in seen_hooks:
                continue
            seen_hooks.add(key)
            clean_name = h.get("clean_name", h["name"])
            event = h["event"]
            matcher = h.get("matcher", "")
            desc = h.get("description", "")
            path = h.get("path", ".claude/settings.json")
            when = f"{event} · {matcher}" if matcher else event
            if desc:
                lines.append(f"- **[`{clean_name}`]({path})** (`{when}`) — {desc}")
            else:
                lines.append(f"- **[`{clean_name}`]({path})** (`{when}`)")
    else:
        lines.append("_(no hooks configured)_")
    lines.append("")

    # ADRs (just count + link)
    lines.append("### Architecture Decision Records\n")
    lines.append(
        f"[`decisions/`](decisions/) holds {len(adrs)} ADR(s)."
        " See [`decisions/README.md`](decisions/README.md) for the full index."
    )
    lines.append("")

    return "\n".join(lines)


def _build_counts() -> str:
    """Build the counts summary line."""
    skills = discover_skills()
    agents = discover_agents()
    hooks = discover_hooks()
    adrs = discover_adrs()

    critics = [a for a in agents if a.get("type") == "critic"]
    generators = [a for a in agents if a.get("type") != "critic"]

    # Deduplicate hooks by (name, event)
    seen = set()
    unique_hooks = []
    for h in hooks:
        key = (h["name"], h["event"])
        if key not in seen:
            seen.add(key)
            unique_hooks.append(h)

    lines = [
        f"> **Auto-generated component counts** (as of last generator run):"
        f" {len(skills)} skill(s),"
        f" {len(critics)} critic(s) + {len(generators)} generator(s),"
        f" {len(unique_hooks)} hook(s),"
        f" {len(adrs)} ADR(s)."
    ]
    return "\n".join(lines)


def _build_critic_list() -> str:
    """Build a markdown bullet list of adversarial critics from the filesystem.

    Discovers critics via discover_agents() (type == 'critic'), sorted by stem.
    Each bullet: **[`name`](path)** — first sentence of frontmatter description.
    Returns a plain bullet list (no trailing newline) suitable for
    {{GENERATED:critic-list}}.
    """
    agents = discover_agents()
    critics = sorted(
        [a for a in agents if a.get("type") == "critic"],
        key=lambda a: a.get("stem", a.get("name", "")),
    )
    lines = []
    for c in critics:
        name = c.get("name") or c["stem"]
        path = c["path"]
        desc = c.get("description", "")
        # Use first sentence only (up to first ". " or end of string)
        first_sentence = desc.split(". ")[0].rstrip(".")
        if first_sentence:
            lines.append(f"- **[`{name}`]({path})** — {first_sentence}.")
        else:
            lines.append(f"- **[`{name}`]({path})**")
    return "\n".join(lines)


def generate_readme() -> None:
    """Read README.template.md, substitute placeholders, write README.md.

    Placeholders:
      {{GENERATED:pipeline-diagram}}  — fixed Mermaid diagram block
      {{GENERATED:component-map}}     — filesystem-derived skills/agents/hooks/ADR map
      {{GENERATED:counts}}            — one-line component count summary
      {{GENERATED:critic-list}}       — filesystem-derived adversarial-critic bullet list

    Idempotent: running twice produces the same README.md.
    No LLM calls — pure stdlib + pathlib.

    Uses _resolve_invoking_repo_root() so that when invoked from a worktree,
    the README is written into THAT worktree's root rather than the script's
    physical location (which may be a sibling worktree on a different branch).
    """
    gen_root = _resolve_invoking_repo_root()
    template_path = gen_root / "README.template.md"
    readme_path = gen_root / "README.md"

    if not template_path.exists():
        print(
            f"ERROR: template not found at {template_path}",
            file=sys.stderr, flush=True,
        )
        sys.exit(1)

    template = template_path.read_text(encoding="utf-8")

    substitutions = {
        "{{GENERATED:pipeline-diagram}}": render_pipeline_mermaid(_get_pipeline_spec()),
        "{{GENERATED:component-map}}": _build_component_map().rstrip("\n"),
        "{{GENERATED:counts}}": _build_counts(),
        "{{GENERATED:critic-list}}": _build_critic_list(),
    }

    result = template
    for placeholder, value in substitutions.items():
        result = result.replace(placeholder, value)

    header = (
        "<!-- AUTO-GENERATED from README.template.md"
        " — edit the template, run the generator. -->\n"
    )
    final = header + result

    readme_path.write_text(final, encoding="utf-8")
    print(f"README.md written ({len(final)} bytes)", flush=True)


if __name__ == "__main__":
    if "--generate-readme" in sys.argv:
        generate_readme()
    else:
        main()
