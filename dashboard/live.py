"""
dashboard/live.py — live-tab backend: live-poll byte-cursor reader + live-progress cache.

Exports for server.py:
    serve_live_poll(cursor_raw) -> dict
    _live_progress_background() -> None
    _live_progress_cache, _live_progress_lock, _live_progress_computing,
    _LIVE_PROGRESS_TTL

Import direction: server <- live (live.py must NOT import the server module).
"""

import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo root — live.py lives at <repo>/dashboard/live.py
# ---------------------------------------------------------------------------
_LIVE_REPO_ROOT = Path(__file__).resolve().parent.parent

# sys.path injection so collector/comparison are importable when live.py is
# imported by server.py (which has already done the same injection, but this
# guards the case where live.py is imported standalone or via CHECK 9).
import sys as _sys
_DASHBOARD_DIR_STR = str(Path(__file__).resolve().parent)
if _DASHBOARD_DIR_STR not in _sys.path:
    _sys.path.insert(0, _DASHBOARD_DIR_STR)

from collector import get_trail  # noqa: E402

# ---------------------------------------------------------------------------
# Live-progress cache — resolves the most recent open PRD + reads its trail.
# Background-thread + 25s TTL, exactly like /api/rollup.  NO gh calls in the
# HTTP handler.
# ---------------------------------------------------------------------------
_live_progress_cache: dict = {}   # {"data": {...}, "ts": float}
_live_progress_computing: bool = False
_live_progress_lock = threading.Lock()
_LIVE_PROGRESS_TTL = 25           # seconds

_WORKFLOW_LOG = _LIVE_REPO_ROOT / ".claude" / "logs" / "workflow-events.jsonl"
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


def _encode_cursor(mtime_int: int, byte_offset: int) -> str:
    """Encode file identity + byte offset as an opaque cursor string.

    Format: "<mtime_int>:<byte_offset>"  (both non-negative integers).
    Clients treat this as opaque and send it back verbatim.
    """
    return f"{mtime_int}:{byte_offset}"


def _decode_cursor(cursor_raw: str) -> tuple[int | None, int]:
    """Decode a cursor string into (mtime_int_or_None, byte_offset).

    Bare-int legacy cursors (from old clients) cannot carry file identity,
    so they decode to (None, 0) which triggers reset:true on the next poll.
    Unknown/malformed cursors also decode to (None, 0) → reset:true.
    """
    if cursor_raw is None:
        return (None, 0)
    s = str(cursor_raw).strip()
    if ":" in s:
        parts = s.split(":", 1)
        try:
            mtime_int = int(parts[0])
            byte_offset = int(parts[1])
            if byte_offset < 0:
                return (None, 0)
            return (mtime_int, byte_offset)
        except (ValueError, IndexError):
            return (None, 0)
    # Bare integer — legacy client; cannot verify file identity → reset
    return (None, 0)


def serve_live_poll(cursor_raw: str) -> dict:
    """Stat the log, seek to cursor, parse only appended bytes.

    Returns {cursor: str, events: list, reset: bool, collector_status: dict}.
    File identity = mtime (truncated to integer seconds) — st_ino is unreliable
    on Windows.  Identity change or size < byte_offset → reset cursor, reset:true.
    Same-size different-content replacement is detected via mtime change.

    Cursor encoding: "<mtime_int>:<byte_offset>" (opaque to clients).
    Bare-int legacy cursors (old clients) → (None, 0) → reset:true on first poll.
    collector_status is read from the in-memory live-progress cache (zero
    extra network cost — same data _build_live_progress already computed).
    """
    log_path = _live_poll_log_path()
    if not log_path.exists():
        return {"cursor": _encode_cursor(0, 0), "events": [], "reset": False,
                "collector_status": _read_collector_status_from_cache()}

    prev_mtime, byte_offset = _decode_cursor(cursor_raw)

    try:
        st = log_path.stat()
        size = st.st_size
        cur_mtime_int = int(st.st_mtime)
    except OSError:
        return {"cursor": _encode_cursor(0, 0), "events": [], "reset": False,
                "collector_status": _read_collector_status_from_cache()}

    reset = False

    # File identity check: mtime mismatch means a different file (even same size)
    if prev_mtime is None or prev_mtime != cur_mtime_int:
        byte_offset = 0
        reset = True

    # Truncation/corruption: byte_offset past end of file
    if byte_offset > size:
        byte_offset = 0
        reset = True

    if byte_offset == size:
        # Nothing new
        return {"cursor": _encode_cursor(cur_mtime_int, byte_offset),
                "events": [], "reset": reset,
                "collector_status": _read_collector_status_from_cache()}

    try:
        with log_path.open("rb") as fh:
            fh.seek(byte_offset)
            chunk = fh.read(size - byte_offset)
    except OSError:
        return {"cursor": _encode_cursor(cur_mtime_int, byte_offset),
                "events": [], "reset": reset,
                "collector_status": _read_collector_status_from_cache()}

    new_offset = byte_offset + len(chunk)
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

    return {"cursor": _encode_cursor(cur_mtime_int, new_offset),
            "events": events, "reset": reset,
            "collector_status": _read_collector_status_from_cache()}


def _read_collector_status_from_cache() -> dict:
    """Read collector_status from the live-progress cache (thread-safe).

    Returns a default dict if the cache has not been populated yet.
    Never raises.
    """
    try:
        with _live_progress_lock:
            data = _live_progress_cache.get("data")
        if data and "collector_status" in data:
            return data["collector_status"]
    except Exception:
        pass
    return {"state": "ok", "label": "Collector OK"}


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


def _resolve_open_prd() -> dict:
    """Return a typed result for the most recent open prd-labeled issue.

    Returns a dict with keys:
        state: "ok" | "empty" | "error"
        number: int | None   — issue number when state == "ok"
        label:  str          — human-readable reason (for error/empty)

    "ok"    — gh succeeded and found an open PRD.
    "empty" — gh succeeded but there is no open PRD.
    "error" — gh CLI unavailable, timed out, or returned non-zero exit.
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
            cwd=str(_LIVE_REPO_ROOT),
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            return {"state": "error", "number": None,
                    "label": "gh CLI unavailable — check auth/PATH"}
        items = json.loads(result.stdout)
        if not items:
            return {"state": "empty", "number": None, "label": "No open PRD"}
        return {"state": "ok", "number": items[0]["number"], "label": ""}
    except FileNotFoundError:
        return {"state": "error", "number": None,
                "label": "gh CLI unavailable — check auth/PATH"}
    except Exception as exc:
        return {"state": "error", "number": None,
                "label": f"gh CLI unavailable — {exc}"}


def _build_live_progress() -> dict:
    """Fetch the most recent open PRD trail and shape the live-progress payload.

    Called from the background thread; never from an HTTP handler.
    """
    pill = _capture_pill_state()
    prd_result = _resolve_open_prd()

    if prd_result["state"] == "error":
        return {
            "prd_number": None,
            "prd_title": None,
            "slices": [],
            "collector_status": {
                "state": "error",
                "label": prd_result["label"],
            },
            "capture_pill": pill,
        }

    if prd_result["state"] == "empty":
        return {
            "prd_number": None,
            "prd_title": None,
            "slices": [],
            "collector_status": {"state": "empty", "label": "No open PRD"},
            "capture_pill": pill,
        }

    prd_number = prd_result["number"]

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
