#!/usr/bin/env python3
"""
dashboard/transcript.py — session transcript reader (PRD #898, slice #899).

Resolves the active Claude Code session transcript JSONL, parses it together
with per-subagent JSONL files, and normalises every record into the event shape
the Live/Trail UI already consumes (same fields as workflow-events.jsonl v2).

Sanitised-path rule (confirmed via filesystem inspection):
  Windows cwd  F:/project_claude/.claude/worktrees/agent-xyz
  -> drive 'F:' -> 'F'
  -> rest of path '/project_claude/.claude/worktrees/agent-xyz'
       separators replaced with '-'  -> 'project_claude-.claude-worktrees-agent-xyz'
  -> joined with '--'  -> 'F--project-claude--claude-worktrees-agent-xyz'
  (matches actual dirs under ~/.claude/projects/)

Resolution order:
  1. env var CLAUDE_TRANSCRIPT_PATH (set by hook context injection, ADR-0057 D4)
  2. Newest *.jsonl under ~/.claude/projects/<sanitised-cwd>/
  3. Newest *.jsonl under ~/.claude/projects/F--project-claude/  (root project fallback)

Defensive parsing: unknown record types and missing fields are silently tolerated;
the reader never raises on malformed input.

Public API:
  resolve_transcript() -> Path | None
  parse_transcript(path: Path) -> list[dict]
  get_session_events() -> dict  (for /api/session-live)

CLI:
  python dashboard/transcript.py --self
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _sanitise_path(cwd: str) -> str:
    """Convert a filesystem cwd into the Claude ~/.claude/projects/<name> form.

    Observed rule (confirmed via filesystem inspection of ~/.claude/projects/):
      Every character that is not alphanumeric or '-' is replaced with '-'.
      This means path separators ('\\', '/'), dots ('.'), colons (':'), and
      underscores ('_') all become hyphens.

    Examples:
      F:\\project_claude                           -> F--project-claude
      F:\\project_claude\\.claude\\worktrees\\xyz  -> F--project-claude--claude-worktrees-xyz
      F:/project_claude/.claude/worktrees/xyz      -> F--project-claude--claude-worktrees-xyz

    The double-dash after the drive letter emerges naturally: 'F:' -> 'F-' and
    the following separator becomes another '-', giving 'F--rest'.
    """
    import re
    # Replace every non-alphanumeric, non-hyphen character with '-'
    sanitised = re.sub(r"[^A-Za-z0-9-]", "-", cwd)
    # Collapse runs of >2 hyphens to exactly 2 (drives produce F-- naturally;
    # we preserve those but squash accidental 3+ runs from adjacent separators).
    sanitised = re.sub(r"-{3,}", "--", sanitised)
    # Strip leading/trailing hyphens
    sanitised = sanitised.strip("-")
    return sanitised


def _claude_projects_root() -> Path:
    """Return ~/.claude/projects path."""
    return Path.home() / ".claude" / "projects"


def _candidate_project_dirs() -> list[Path]:
    """Return ordered list of candidate project dirs to search for sessions.

    Priority:
      1. Dir matching the current working directory (most specific).
      2. Root project dir F--project-claude (fallback for worktree sessions).
    """
    projects = _claude_projects_root()
    candidates: list[Path] = []

    try:
        cwd = os.getcwd()
        sanitised = _sanitise_path(cwd)
        specific = projects / sanitised
        if specific.exists():
            candidates.append(specific)
    except Exception:
        pass

    # Fallback: main project dir (handles hooks-dark worktree sessions)
    fallback = projects / "F--project-claude"
    if fallback.exists() and fallback not in candidates:
        candidates.append(fallback)

    return candidates


def _newest_jsonl_in(directory: Path) -> Path | None:
    """Return the newest *.jsonl file directly inside directory, or None."""
    try:
        files = [f for f in directory.iterdir()
                 if f.is_file() and f.suffix == ".jsonl"]
        if not files:
            return None
        return max(files, key=lambda f: f.stat().st_mtime)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Transcript resolution
# ---------------------------------------------------------------------------

def resolve_transcript() -> Path | None:
    """Resolve the path to the active session transcript.

    Resolution order:
      1. CLAUDE_TRANSCRIPT_PATH env var (hook-injected, ADR-0057 D4).
      2. Newest *.jsonl in the sanitised-cwd project dir.
      3. Newest *.jsonl in the F--project-claude fallback dir.

    Returns None when no transcript can be found.
    """
    # 1. Hook-injected path
    env_path = os.environ.get("CLAUDE_TRANSCRIPT_PATH", "").strip()
    if env_path:
        p = Path(env_path)
        if p.exists() and p.is_file():
            return p

    # 2 + 3. Scan candidate project dirs
    for project_dir in _candidate_project_dirs():
        found = _newest_jsonl_in(project_dir)
        if found is not None:
            return found

    return None


# ---------------------------------------------------------------------------
# Record normalisation
# ---------------------------------------------------------------------------

_RECORD_TYPES_KEEP = {"user", "assistant"}


def _normalise_record(record: dict, source_file: str, session_id: str) -> dict | None:
    """Normalise a single transcript record into the Live/Trail UI event shape.

    The UI (Lane B + /api/live-poll) consumes workflow-events.jsonl v2 events
    with these fields:
      v, ts, session_id, event, src, [subagent_type, input, ...]

    Transcript records use:
      type: "user" | "assistant" | ...
      timestamp: ISO-8601 string
      message.content: list of {type, ...} items
      agentId: subagent identifier (in subagent files)
      uuid, parentUuid

    Mapping:
      type=user   + toolUseResult  -> event="tool_result"
      type=user   (no tool result) -> event="user_prompt" with prompt excerpt
      type=assistant + tool_use    -> event="tool_use"    (one per tool call)
      type=assistant (text only)   -> event="assistant_response"
      Any type=assistant containing name="Agent"/"Task" tool_use -> event="agent_start"

    Returns None for records that should be dropped (unknown types, queue-ops, etc).
    """
    rec_type = record.get("type", "")
    if rec_type not in _RECORD_TYPES_KEEP:
        return None

    ts = record.get("timestamp", "")
    uuid = record.get("uuid", "")
    agent_id = record.get("agentId", "")

    base: dict[str, Any] = {
        "v": 2,
        "ts": ts,
        "session_id": session_id,
        "src": "transcript",
        "_transcript_uuid": uuid,
        "_source_file": source_file,
    }
    if agent_id:
        base["_agent_id"] = agent_id

    msg = record.get("message", {})
    if not isinstance(msg, dict):
        msg = {}

    content = msg.get("content", [])
    if not isinstance(content, list):
        content = []

    if rec_type == "user":
        # Check for tool_result
        tool_result_item = None
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_result":
                tool_result_item = item
                break

        if tool_result_item is not None:
            ev = dict(base)
            ev["event"] = "tool_result"
            ev["tool_use_id"] = tool_result_item.get("tool_use_id", "")
            raw_content = tool_result_item.get("content", "")
            if isinstance(raw_content, list):
                # list of content blocks — join text parts
                parts = []
                for block in raw_content:
                    if isinstance(block, dict):
                        parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        parts.append(block)
                raw_content = "\n".join(parts)
            ev["content_excerpt"] = str(raw_content)[:200]
            ev["is_error"] = bool(tool_result_item.get("is_error"))
            return ev
        else:
            # Plain user message — extract text
            ev = dict(base)
            ev["event"] = "user_prompt"
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            prompt = " ".join(text_parts)[:200]
            ev["prompt"] = prompt
            return ev

    elif rec_type == "assistant":
        # Check for tool_use items in content
        tool_use_items = [
            item for item in content
            if isinstance(item, dict) and item.get("type") == "tool_use"
        ]

        # Determine if this is an agent dispatch (Agent or Task tool)
        agent_dispatch_items = [
            item for item in tool_use_items
            if item.get("name") in ("Agent", "Task")
        ]

        if agent_dispatch_items:
            # Emit one event per Agent/Task dispatch
            events = []
            for item in agent_dispatch_items:
                ev = dict(base)
                ev["event"] = "agent_start"
                tool_input = item.get("input", {})
                if isinstance(tool_input, str):
                    try:
                        tool_input = json.loads(tool_input)
                    except Exception:
                        tool_input = {"raw": tool_input}
                ev["subagent_type"] = tool_input.get(
                    "subagent_type", item.get("name", "")
                )
                ev["input"] = str(tool_input.get("prompt", ""))[:120]
                ev["tool_use_id"] = item.get("id", "")
                ev["description"] = str(tool_input.get("description", ""))[:80]
                events.append(ev)
            # Return first; caller handles multi-return by calling this per-item
            # (here we only return the first to keep 1-in/1-out; the caller loops)
            return events[0] if len(events) == 1 else events  # type: ignore[return-value]

        elif tool_use_items:
            # Regular tool use — emit one event for the first tool call
            # (the Walk below handles duplicates per record)
            item = tool_use_items[0]
            ev = dict(base)
            ev["event"] = "tool_use"
            ev["tool_name"] = item.get("name", "")
            tool_input = item.get("input", {})
            if isinstance(tool_input, str):
                try:
                    tool_input = json.loads(tool_input)
                except Exception:
                    tool_input = {"raw": str(tool_input)[:80]}
            ev["tool_input_excerpt"] = str(tool_input)[:120]
            ev["tool_use_id"] = item.get("id", "")
            return ev
        else:
            # Text-only assistant response
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            text = " ".join(text_parts)
            if not text:
                return None  # empty/thinking-only response — drop
            ev = dict(base)
            ev["event"] = "assistant_response"
            ev["assistant_tail"] = text[:200]
            return ev

    return None


def _normalise_all_tool_uses(record: dict, source_file: str, session_id: str) -> list[dict]:
    """Like _normalise_record but emits ONE event per tool_use item in content.

    Used when an assistant message contains multiple tool calls (e.g. parallel
    Bash + Grep).  Returns an empty list for non-assistant records or records
    with no tool_use items.
    """
    if record.get("type") != "assistant":
        return []

    msg = record.get("message", {})
    if not isinstance(msg, dict):
        return []
    content = msg.get("content", [])
    if not isinstance(content, list):
        return []

    ts = record.get("timestamp", "")
    uuid = record.get("uuid", "")
    agent_id = record.get("agentId", "")
    base: dict[str, Any] = {
        "v": 2,
        "ts": ts,
        "session_id": session_id,
        "src": "transcript",
        "_transcript_uuid": uuid,
        "_source_file": source_file,
    }
    if agent_id:
        base["_agent_id"] = agent_id

    events: list[dict] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "tool_use":
            continue
        tool_name = item.get("name", "")
        tool_input = item.get("input", {})
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except Exception:
                tool_input = {"raw": str(tool_input)[:80]}

        if tool_name in ("Agent", "Task"):
            ev = dict(base)
            ev["event"] = "agent_start"
            ev["subagent_type"] = tool_input.get("subagent_type", tool_name)
            ev["input"] = str(tool_input.get("prompt", ""))[:120]
            ev["tool_use_id"] = item.get("id", "")
            ev["description"] = str(tool_input.get("description", ""))[:80]
            events.append(ev)
        else:
            ev = dict(base)
            ev["event"] = "tool_use"
            ev["tool_name"] = tool_name
            ev["tool_input_excerpt"] = str(tool_input)[:120]
            ev["tool_use_id"] = item.get("id", "")
            events.append(ev)

    return events


# ---------------------------------------------------------------------------
# Transcript parser
# ---------------------------------------------------------------------------

def _parse_session_id_from_path(path: Path) -> str:
    """Derive session_id from a transcript file path.

    Main transcript: <session-uuid>.jsonl -> session-uuid
    Subagent file:   subagents/agent-<hex>.jsonl -> agent-<hex>
    """
    return path.stem  # filename without extension


def _read_jsonl_records(path: Path) -> list[dict]:
    """Read all valid JSON objects from a JSONL file.

    Defensive: skips blank lines and malformed JSON without raising.
    """
    records: list[dict] = []
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        records.append(obj)
                except Exception:
                    continue
    except Exception:
        pass
    return records


def parse_transcript(path: Path) -> list[dict]:
    """Parse a main session transcript and its subagent files.

    Reads <path> (main) and <path.parent>/<path.stem>/subagents/*.jsonl.
    Returns a list of normalised events sorted by timestamp.

    Never raises; returns [] on error.
    """
    if not path.exists():
        return []

    session_id = _parse_session_id_from_path(path)
    events: list[dict] = []

    # 1. Parse main transcript
    _parse_file_into(path, str(path), session_id, events)

    # 2. Parse subagents directory
    subagents_dir = path.parent / path.stem / "subagents"
    if subagents_dir.is_dir():
        try:
            sub_files = [
                f for f in subagents_dir.iterdir()
                if f.is_file() and f.suffix == ".jsonl"
            ]
            # Sort by name for deterministic ordering
            for sub_file in sorted(sub_files):
                # subagent session id is derived from the subagent filename
                sub_sid = sub_file.stem
                _parse_file_into(sub_file, str(sub_file), sub_sid, events)
        except Exception:
            pass

    # Sort by timestamp (ISO-8601 sorts lexicographically)
    events.sort(key=lambda e: e.get("ts", ""))
    return events


def _parse_file_into(
    path: Path, source_label: str, session_id: str, out: list[dict]
) -> None:
    """Parse one JSONL file and append normalised events to out.

    Uses _normalise_all_tool_uses for assistant records (multi-tool aware) and
    falls back to _normalise_record for user records.
    """
    records = _read_jsonl_records(path)
    for record in records:
        rec_type = record.get("type", "")

        if rec_type == "assistant":
            # Try multi-tool-use expansion first
            tool_evs = _normalise_all_tool_uses(record, source_label, session_id)
            if tool_evs:
                out.extend(tool_evs)
            else:
                # Text-only or thinking-only response
                ev = _normalise_record(record, source_label, session_id)
                if ev is not None and isinstance(ev, dict):
                    out.append(ev)
        elif rec_type == "user":
            ev = _normalise_record(record, source_label, session_id)
            if ev is not None and isinstance(ev, dict):
                out.append(ev)
        # All other types (queue-operation, attachment, last-prompt, etc.) are dropped


# ---------------------------------------------------------------------------
# Mtime cache for /api/session-live
# ---------------------------------------------------------------------------

_cache: dict = {
    "path": None,       # Path | None
    "mtime": None,      # float | None
    "events": [],       # list[dict]
    "source": "",       # str — human-readable source label
}


def get_session_events() -> dict:
    """Return the current-session events dict for /api/session-live.

    Caches by file mtime — no full re-parse if the file has not changed.

    Returns:
      {
        "events": [...],   # normalised event list
        "source": str,     # transcript file path (or empty)
        "event_count": int,
        "error": str | None,
      }
    """
    global _cache

    path = resolve_transcript()
    if path is None:
        return {
            "events": [],
            "source": "",
            "event_count": 0,
            "error": "no transcript file found",
        }

    try:
        mtime = path.stat().st_mtime
    except Exception as exc:
        return {
            "events": [],
            "source": str(path),
            "event_count": 0,
            "error": f"stat failed: {exc}",
        }

    # Cache hit
    if _cache["path"] == path and _cache["mtime"] == mtime:
        return {
            "events": _cache["events"],
            "source": _cache["source"],
            "event_count": len(_cache["events"]),
            "error": None,
        }

    # Parse and update cache
    try:
        events = parse_transcript(path)
    except Exception as exc:
        return {
            "events": [],
            "source": str(path),
            "event_count": 0,
            "error": f"parse failed: {exc}",
        }

    _cache["path"] = path
    _cache["mtime"] = mtime
    _cache["events"] = events
    _cache["source"] = str(path)

    return {
        "events": events,
        "source": str(path),
        "event_count": len(events),
        "error": None,
    }


# ---------------------------------------------------------------------------
# CLI: --self
# ---------------------------------------------------------------------------

def _cli_self() -> None:
    """Print resolved transcript path, event count, and last few events."""
    path = resolve_transcript()
    if path is None:
        print("ERROR: no transcript file found", file=sys.stderr)
        print(f"Searched: {_candidate_project_dirs()}", file=sys.stderr)
        sys.exit(1)

    print(f"Transcript path : {path}")
    print(f"File size       : {path.stat().st_size} bytes")

    result = get_session_events()
    events = result["events"]
    count = result["event_count"]
    err = result.get("error")

    print(f"Event count     : {count}")
    if err:
        print(f"Error           : {err}", file=sys.stderr)

    if count == 0:
        print("(no normalised events — transcript may be empty or all non-user/assistant records)")
        sys.exit(0)

    print("\nLast 5 events:")
    for ev in events[-5:]:
        ts = ev.get("ts", "")[:19]
        event_type = ev.get("event", "?")
        tool = ev.get("tool_name", "")
        subtype = ev.get("subagent_type", "")
        detail = tool or subtype or ev.get("prompt", "")[:60] or ""
        print(f"  {ts}  {event_type:<22}  {detail}")

    sys.exit(0)


if __name__ == "__main__":
    if "--self" in sys.argv:
        _cli_self()
    else:
        print("Usage: python dashboard/transcript.py --self")
        sys.exit(1)
