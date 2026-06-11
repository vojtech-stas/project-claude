"""
dashboard/events.py — workflow-events.jsonl tail-seek reader for /api/runs.

Exports:
    iter_lines_reversed(path, chunk_size) -> generator
    serve_runs(query, is_valid_v2_fn, fixture_re) -> dict

Import direction: server <- events (this module must NOT import server).
"""

import json
import re
from pathlib import Path

# Reader-side fixture-pattern guard — mirrors the writer's FIXTURE_PATTERN in
# log-tool-event.sh so the server defensively drops synthetic sids even if the
# writer's routing was bypassed (e.g. direct file writes during testing).
FIXTURE_SID_RE = re.compile(
    r"^(demo|test|verify|fixture|manual|sess-)", re.IGNORECASE
)


def is_valid_v2_event(obj: dict) -> bool:
    """Return True iff obj is a schema-v2 event with a non-empty, non-fixture session_id."""
    if obj.get("v") != 2:
        return False
    sid = obj.get("session_id", "")
    if not sid:
        return False
    if FIXTURE_SID_RE.match(sid):
        return False
    return True


# ---------------------------------------------------------------------------
# Tail-seek helper — yields lines from a text file in reverse order.
# Reads in 64 KiB chunks from the end; never loads the whole file.
# ---------------------------------------------------------------------------

def iter_lines_reversed(path: Path, chunk_size: int = 65536):
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


def serve_runs(query: dict, log_path: Path) -> dict:
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

    Implementation: reads the file backwards in 64 KiB chunks across the full
    window to collect ALL matching events regardless of interleaving.  Cost is
    O(file size); correctness requires the full-window collect (no break-early).  Break-early
    is an invalid optimisation for interleaved sessions — two concurrent sessions
    can alternate lines throughout the file, so a contiguous-block assumption
    produces truncated results (slice #739).

    For ?before=<cursor>: after the skip phase the cursor sid is permanently
    excluded so it cannot reappear in the collected page even when its lines
    are interleaved with the first N collected sessions.
    """
    if not log_path.exists():
        # Return appropriate empty shape depending on query mode
        if (query.get("session") or [""])[0]:
            return {"run": None}
        return {"runs": [], "rejected_lines": 0}

    # --- ?session=<id> branch: return ONE session's full events ---
    session_id_filter = (query.get("session") or [""])[0]
    if session_id_filter:
        try:
            lines_reversed = iter_lines_reversed(log_path)
            events_reversed: list = []
            for raw in lines_reversed:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue
                if not is_valid_v2_event(obj):
                    continue
                sid = obj.get("session_id", "")
                if sid == session_id_filter:
                    events_reversed.append(obj)
                # Do NOT break on non-matching lines: concurrent sessions
                # interleave throughout the file — the target session's events
                # may be scattered in non-contiguous blocks (slice #739 fix).
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
        lines_reversed = iter_lines_reversed(log_path)

        # Collect session groups in reverse insertion order (newest first).
        sessions_newest_first: list = []  # list of [sid, first_ts, last_ts, count]
        sid_to_idx: dict = {}

        # When before_cursor is set we skip all sessions that appear AFTER
        # the cursor in the file (i.e., sessions newer than the cursor when
        # reading reversed).  We track whether we have SEEN the cursor
        # session at all; only AFTER we first encounter it AND then move past
        # it (into a different session_id) do we start collecting.
        cursor_seen = False  # have we observed at least one cursor-session line?
        in_before_skip = (before_cursor is not None)

        # Track the number of NEW (distinct) sessions collected so we know
        # when to stop discovering new sessions.  We always continue scanning
        # to update already-seen sessions (interleave-safe full-window collect).
        new_sessions_collected = 0

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
            if not is_valid_v2_event(obj):
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

            # After the skip phase, permanently exclude the cursor sid so it
            # cannot reappear in the collected page (interleaved lines fix,
            # slice #739).
            if before_cursor is not None and sid == before_cursor:
                continue

            ts = obj.get("ts", "")
            if sid not in sid_to_idx:
                # New session: only collect if we haven't reached n yet.
                if new_sessions_collected >= n:
                    # We have enough distinct sessions.  Continue scanning to
                    # update already-seen sessions' counts (full-window collect),
                    # but skip any brand-new sid we encounter.
                    continue
                sid_to_idx[sid] = len(sessions_newest_first)
                new_sessions_collected += 1
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
