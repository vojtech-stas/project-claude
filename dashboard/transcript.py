#!/usr/bin/env python3
"""
dashboard/transcript.py — session transcript reader (PRD #898, slices #899/#901).

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
  1. env var CLAUDE_TRANSCRIPT_PATH (may be set externally — planned hook injection, not yet implemented; falls through to autodiscovery)
  2. Newest *.jsonl under ~/.claude/projects/<sanitised-cwd>/
  3. Newest *.jsonl under ~/.claude/projects/F--project-claude/  (root project fallback)

Defensive parsing: unknown record types and missing fields are silently tolerated;
the reader never raises on malformed input.

Public API:
  resolve_transcript() -> Path | None
  parse_transcript(path: Path) -> list[dict]
  get_session_events() -> dict  (for /api/session-live)
  build_firing_tree(path: Path) -> dict  (for /api/session-firing)
  get_session_firing() -> dict  (cached, BLOCKING — see serve_session_firing)
  serve_session_firing() -> dict  (NON-BLOCKING — HTTP handler, issue #1061)
    Stale-while-revalidate: warm cache -> immediate; cold/stale -> returns
    {"status":"computing"} or last-known+refreshing, kicks a background
    daemon thread to build. Mirrors prd_firing.serve_prd_firing() (#962).
  get_runtime_reading() -> dict  (cached, for /api/runtime-reading)

CLI:
  python dashboard/transcript.py --self
  python dashboard/transcript.py --firing
"""

from __future__ import annotations

import json
import os
import subprocess
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
    # 1. Externally-set path (planned hook injection — not yet implemented;
    #    falls through to autodiscovery when not set)
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
# Per-PRD firing tree (slice #901)
# ---------------------------------------------------------------------------
# Maps each subagent transcript (subagents/agent-*.jsonl) to its parent Agent
# dispatch in the MAIN transcript via the meta.json toolUseId field.
# Extracts: agent type, start/end timestamps, verdict (CRITIC/GENERATOR trailer).
# Groups dispatches by PRD label derived from the description field.
# ---------------------------------------------------------------------------

import re as _re

# Patterns for extracting trailers from subagent final assistant messages
_VERDICT_RE = _re.compile(r"^\s*VERDICT\s*:\s*(\w+)\s*$", _re.IGNORECASE | _re.MULTILINE)
_RESULT_RE  = _re.compile(r"^\s*RESULT\s*:\s*(\w+)\s*$", _re.IGNORECASE | _re.MULTILINE)
# Pattern for extracting issue numbers from description strings
# e.g. "implementer for #901", "reviewer PR #823 (closing slice)", "backlog-critic for #725"
_ISSUE_RE   = _re.compile(r"#(\d+)")

# Pattern to extract parent PRD from a slice body.
# Handles all observed canonical formats:
#   "Walking-skeleton slice of PRD #956 ..."   (PRD #956-era slices)
#   "slice 2 of PRD #737."
#   "Parent: PRD #123"
#   "## Parent\n\nPRD #713 — desc"            (older slice template)
#   "Part of PRD #993 ..."                    (real slice template — fix #1022)
_PARENT_PRD_BODY_RE = _re.compile(
    r"(?:"
    r"(?:(?:slice\s+\d+\s+of|walking-skeleton\s+slice\s+of)\s+PRD)"
    r"|(?:part\s+of\s+PRD)"
    r"|(?:parent\s*:?\s*PRD)"
    r"|(?:##\s*[Pp]arent\s*\n+\s*PRD)"
    r")\s+#(\d+)",
    _re.IGNORECASE | _re.MULTILINE,
)

# Pattern to extract Closes #N from a PR body (mirrors prd_firing.py)
_PR_CLOSES_RE = _re.compile(
    r"(?:Closes|closes|Fixes|fixes|Resolves|resolves)\s+#(\d+)",
    _re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# gh CLI helper (mirrors prd_firing._gh_run pattern)
# ---------------------------------------------------------------------------

def _gh_run_transcript(args: list[str], timeout: int = 15) -> tuple[int, str]:
    """Run a gh CLI command; return (returncode, stdout).

    Uses UTF-8 with errors='replace' to avoid cp1252 decode failures on
    Windows (mirrors prd_firing._gh_run — issue #934 root cause).
    Returns (1, '') when gh is not found or times out (fallback-safe).
    """
    try:
        r = subprocess.run(
            ["gh"] + args,
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        return r.returncode, r.stdout or ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 1, ""


# ---------------------------------------------------------------------------
# Disk cache for gh issue/PR → parent-PRD lookups (perf fix, slice #959)
# ---------------------------------------------------------------------------
# The mapping is immutable once a slice/PR exists, so we cache permanently.
# Location: .claude/cache/prd-correlation-cache.json (gitignored via cache/).
# On lookup: check disk → in-process → only then gh; write-through on gh hit.
# ---------------------------------------------------------------------------

def _disk_cache_path() -> Path:
    """Return the path to the persistent PRD-correlation disk cache file.

    Location: <repo-root>/.claude/cache/prd-correlation-cache.json
    The .claude/cache/ directory is gitignored; the mapping is append-only
    (immutable once a slice/PR is created, so we never invalidate).

    Falls back to a sibling of this file if the repo root cannot be found.
    """
    # Walk up from this file to find the repo root (contains .git)
    here = Path(__file__).resolve()
    for parent in [here.parent, here.parent.parent, here.parent.parent.parent]:
        if (parent / ".git").exists():
            cache_dir = parent / ".claude" / "cache"
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            return cache_dir / "prd-correlation-cache.json"
    # Fallback: next to this file
    return here.parent / "prd-correlation-cache.json"


_disk_cache_lock_flag: bool = False  # simple re-entrancy guard (not thread-safe)
_disk_cache_data: dict[str, int | None] | None = None  # loaded once, written through


def _load_disk_cache() -> dict[str, int | None]:
    """Load the disk cache from JSON file.

    Keys are stringified issue/PR numbers; values are parent PRD ints or null.
    Returns an empty dict if the file is missing or malformed.
    """
    global _disk_cache_data
    if _disk_cache_data is not None:
        return _disk_cache_data

    p = _disk_cache_path()
    try:
        with p.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            _disk_cache_data = data
            return _disk_cache_data
    except Exception:
        pass
    _disk_cache_data = {}
    return _disk_cache_data


def _write_disk_cache(data: dict) -> None:
    """Persist the disk cache to JSON (write-through on every gh resolve)."""
    p = _disk_cache_path()
    try:
        with p.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        pass  # disk write failure is non-fatal; in-process cache still works


# ---------------------------------------------------------------------------
# In-process cache for gh issue/PR lookups
# ---------------------------------------------------------------------------

# Maps issue/PR number -> parent PRD number (int) or None (known non-slice)
# or the sentinel _GH_UNAVAILABLE (str) when gh failed.
_GH_UNAVAILABLE = "__gh_unavailable__"

# Sentinel returned by _resolve_slice_to_prd when the issue IS a prd-labeled
# issue itself (not a slice of another PRD).  Distinct from None, which means
# "not a prd-labeled issue AND no parent PRD found in body".
# This lets resolve_dispatch_to_prd distinguish the two cases:
#   _IS_PRD  → the issue is a genuine PRD → return N
#   None     → the issue is NOT a PRD and has no resolvable parent → return None
_IS_PRD = "__is_prd__"

_prd_cache: dict[int, "int | str | None"] = {}
# Timestamp of last successful gh call (used to expire cache on long runs)
_prd_cache_ts: float = 0.0
_PRD_CACHE_TTL = 300.0  # 5 minutes


def _prd_cache_reset_if_stale() -> None:
    """Expire the cache if older than _PRD_CACHE_TTL seconds."""
    global _prd_cache, _prd_cache_ts
    if time.time() - _prd_cache_ts > _PRD_CACHE_TTL:
        _prd_cache = {}
        _prd_cache_ts = time.time()


def _parent_prd_from_issue_body(body: str) -> int | None:
    """Extract parent PRD number from a slice issue body, or None."""
    if not body:
        return None
    m = _PARENT_PRD_BODY_RE.search(body)
    if m:
        return int(m.group(1))
    return None


# Module-level cached repo slug (owner/name) for sub-issue parent API calls.
_transcript_repo_slug: str | None = None


def _get_repo_slug_for_transcript() -> str | None:
    """Return the GitHub repo slug (owner/name) for sub-issue API calls.

    Derived via: gh repo view --json nameWithOwner.
    Result is module-level cached after the first successful call.
    Returns None when gh is unavailable (callers must handle gracefully).
    """
    global _transcript_repo_slug
    if _transcript_repo_slug is not None:
        return _transcript_repo_slug
    rc, stdout = _gh_run_transcript(
        ["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
        timeout=10,
    )
    if rc == 0:
        slug = stdout.strip()
        if "/" in slug:
            _transcript_repo_slug = slug
            return _transcript_repo_slug
    return None


def _fetch_sub_issue_parent(n: int) -> "int | None | str":
    """Query the native GitHub sub-issue parent endpoint for issue N.

    Uses: gh api repos/{owner}/{repo}/issues/{n}/parent --jq .number

    Returns:
      int           — parent issue number (authoritative sub-issue link exists)
      None          — issue has no sub-issue parent (404 or 'null' response)
      _GH_UNAVAILABLE — gh transport failure or repo slug unavailable

    Fix for issue #1022: this is the authoritative resolution path — queried
    BEFORE the body-parse fallback in _resolve_slice_to_prd.
    """
    slug = _get_repo_slug_for_transcript()
    if slug is None:
        return _GH_UNAVAILABLE
    rc, stdout = _gh_run_transcript(
        ["api", f"repos/{slug}/issues/{n}/parent", "--jq", ".number"],
        timeout=15,
    )
    if rc != 0:
        # Non-zero exit: either transport failure or 404 (no parent).
        # gh api returns rc=1 on HTTP 404 — treat as "no parent" (None).
        # We can't distinguish transport failure from 404 here, so we treat
        # both as None (fall through to body parse).  A true transport failure
        # will also fail the subsequent issue-view call and return _GH_UNAVAILABLE.
        return None
    text = stdout.strip()
    if not text or text == "null":
        return None
    try:
        return int(text)
    except (ValueError, TypeError):
        return None


def _resolve_slice_to_prd(slice_n: int) -> "int | str | None":
    """Resolve a slice issue number to its parent PRD.

    Returns:
      int          — the parent PRD number (issue is a slice with a known parent)
      _IS_PRD      — issue IS a prd-labeled issue itself (no parent PRD)
      None         — issue is NOT prd-labeled AND no parent PRD found in body
                     (not a PRD, unresolvable — caller should return None/non-PRD)
      _GH_UNAVAILABLE — gh call failed; caller should fall back

    Fix (issue #1018): previously returned None for BOTH 'is a PRD' and
    'not a PRD, no parent found' cases, causing resolve_dispatch_to_prd to
    treat the second case as a phantom PRD node.  Now returns _IS_PRD for the
    'is a PRD' case so the caller can distinguish them.

    Fix (issue #1022): added two resolution improvements:
      - _PARENT_PRD_BODY_RE now also matches "Part of PRD #N" wording.
      - After prd-label check, query native sub-issue parent endpoint as
        authoritative fallback (fix #1027: body-parse is tried FIRST since the
        body is already fetched, saving an extra gh round-trip in the common case).

    Fix (issue #1027): body-first reorder — try _parent_prd_from_issue_body
    BEFORE _fetch_sub_issue_parent.  The body is already in hand from the
    gh issue view call; parsing it is free.  Only fall back to the sub-issue
    /parent endpoint when the body yields no parent reference.  This halves
    gh calls for the common case (slice body says "Part of PRD #N").

    Strategy:
      1. Fetch issue N with --json number,labels,body.
      2. If labeled 'prd': return _IS_PRD (is a genuine PRD itself).
      3. Parse body for parent PRD patterns (incl. 'Part of PRD #N') — FREE,
         body already fetched in step 1.
      4. If body yields a parent: return that PRD number (no /parent call).
      5. Query native sub-issue parent endpoint (authoritative fallback).
      6. If found: return parent int.
      7. Otherwise: return None (not a PRD, no parent found).
    """
    rc, stdout = _gh_run_transcript([
        "issue", "view", str(slice_n),
        "--json", "number,labels,body",
    ])
    if rc != 0 or not stdout.strip():
        return _GH_UNAVAILABLE

    try:
        data = json.loads(stdout)
    except Exception:
        return _GH_UNAVAILABLE

    labels = data.get("labels", [])
    label_names = {lbl.get("name", "") for lbl in labels}

    if "prd" in label_names:
        # Issue IS a genuine PRD — signal this explicitly so the caller
        # can return N (not None) without conflating with 'no parent found'.
        return _IS_PRD

    # Fix #1027 (body-first reorder): parse the body FIRST — it's already
    # fetched from the gh issue view call above, so this is free.  For the
    # common case where a slice body says "Part of PRD #N", this avoids the
    # extra round-trip to the sub-issue /parent endpoint entirely.
    body = data.get("body", "")
    parent = _parent_prd_from_issue_body(body)
    if parent is not None:
        return parent

    # Body parse yielded no parent → fall through to the authoritative native
    # sub-issue parent endpoint (handles slices with a GitHub sub-issue link
    # but no "Part of PRD #N" text in body — rare but real).
    # Fix #1022 — this endpoint is now the FALLBACK (was previously first).
    sub_parent = _fetch_sub_issue_parent(slice_n)
    if isinstance(sub_parent, int):
        return sub_parent
    # sub_parent is None (no link) or _GH_UNAVAILABLE (transport failure) —
    # fall through to the final None return.

    # Not a prd-labeled issue AND no parent PRD pattern found in body.
    # Return None to signal 'non-PRD, unresolvable' — caller must NOT treat
    # this as a PRD node (fix for issue #1018 phantom PRD bug).
    return None


def _resolve_pr_to_prd(pr_n: int) -> "int | str | None":
    """Resolve a PR number to its parent PRD via Closes #slice → slice → PRD.

    Returns:
      int   — the parent PRD number
      None  — could not resolve
      _GH_UNAVAILABLE — gh call failed
    """
    rc, stdout = _gh_run_transcript([
        "pr", "view", str(pr_n),
        "--json", "number,body",
    ])
    if rc != 0 or not stdout.strip():
        return _GH_UNAVAILABLE

    try:
        data = json.loads(stdout)
    except Exception:
        return _GH_UNAVAILABLE

    body = data.get("body", "")
    closes_nums = [int(m) for m in _PR_CLOSES_RE.findall(body)]

    if not closes_nums:
        return None

    # Try each closed issue as a potential slice
    for slice_candidate in closes_nums:
        result = _resolve_slice_to_prd(slice_candidate)
        if result is _GH_UNAVAILABLE:
            return _GH_UNAVAILABLE
        if result is _IS_PRD:
            # PR closes a prd-labeled issue directly — that IS the PRD
            return slice_candidate
        if isinstance(result, int):
            return result

    return None


def _resolve_dispatch_to_prd_detailed(n: int) -> "tuple[int | None, bool]":
    """Map a dispatch issue/PR number to its parent PRD number, AND report
    whether gh transport was actually healthy for this resolution.

    This is the detailed sibling of resolve_dispatch_to_prd() (public API,
    unchanged for backward compatibility — see #1030). It exists so callers
    that need to distinguish "gh succeeded, genuinely no PRD parent" from
    "gh transport failed" (e.g. _derive_prd_label's label text) can do so,
    without changing the int|None contract other callers/tests depend on.

    Returns (result, gh_ok):
      result — int (parent PRD) or None (unresolvable / non-PRD / gh failure)
      gh_ok  — True  if gh transport succeeded (result is either a resolved
                      PRD or a genuine non-PRD determination)
               False if gh transport itself failed (_GH_UNAVAILABLE) — the
                      None result here is NOT a "no PRD parent" fact, it's
                      "we don't know because gh didn't answer".

    Fix (issue #1030): previously resolve_dispatch_to_prd() alone collapsed
    both outcomes to None, so _derive_prd_label always guessed "gh
    unavailable" for any None — even when gh had actually succeeded and the
    issue simply had no PRD parent.
    """
    _prd_cache_reset_if_stale()

    # 1. Check in-process cache first (fastest path)
    if n in _prd_cache:
        cached = _prd_cache[n]
        if cached is _GH_UNAVAILABLE:
            return None, False
        return cached, True  # type: ignore[return-value]

    # 2. Check disk cache (warm path; avoids gh on restart)
    disk_data = _load_disk_cache()
    disk_key = str(n)
    if disk_key in disk_data:
        val = disk_data[disk_key]
        # Disk stores: int (resolved parent PRD or self for a PRD issue),
        # or None (gh was unavailable at write time — retry gh now).
        if val is None:
            # Could not resolve (gh was unavailable at write time) — retry gh
            pass  # fall through to gh
        else:
            _prd_cache[n] = val
            return val, True  # type: ignore[return-value]

    # 3. Try gh (slow path)
    result = _resolve_slice_to_prd(n)

    if result is _GH_UNAVAILABLE:
        # gh unavailable — try as PR as a secondary attempt
        pr_result = _resolve_pr_to_prd(n)
        if pr_result is _GH_UNAVAILABLE or pr_result is None:
            _prd_cache[n] = _GH_UNAVAILABLE
            # Do NOT write None to disk for gh failures — we want to retry on restart
            return None, False
        _prd_cache[n] = pr_result
        disk_data[disk_key] = pr_result
        _write_disk_cache(disk_data)
        return pr_result, True  # type: ignore[return-value]

    if result is _IS_PRD:
        # Issue IS a genuine prd-labeled issue — return N (it IS the PRD).
        _prd_cache[n] = n
        disk_data[disk_key] = n
        _write_disk_cache(disk_data)
        return n, True

    if result is None:
        # Issue is NOT prd-labeled AND has no resolvable parent PRD body.
        # Fix #1018: do NOT treat this as a phantom 'PRD #N' node.
        # Return None so the UI routes it to the maintenance/non-PRD bucket.
        # Cache in-process only (same as gh-unavailable): the label set on a
        # non-prd issue can change (e.g. promotion to prd), so we don't persist
        # None to disk — the next session will re-verify via gh.
        # gh_ok=True: this IS a genuine non-PRD determination, gh succeeded.
        _prd_cache[n] = None  # type: ignore[assignment]
        return None, True

    # result is the parent PRD int (slice with a known parent)
    _prd_cache[n] = result
    disk_data[disk_key] = result
    _write_disk_cache(disk_data)
    return result, True  # type: ignore[return-value]


def resolve_dispatch_to_prd(n: int) -> "int | None":
    """Map a dispatch issue/PR number to its parent PRD number.

    This is the primary correlation helper for slice #958 (PRD #956 §2 #1).
    Perf fix (slice #959 / captured #962): checks disk cache before gh.
    Bug fix (issue #1018): only prd-labeled issues become PRD firing nodes;
    non-prd-labeled issues with no resolvable parent return None (non-PRD).

    Given a number N extracted from a dispatch description:
      - If N is a PRD issue:      return N.
      - If N is a slice issue:    return its parent PRD.
      - If N looks like a PR:     resolve PR → Closes-slice → PRD.
      - If gh is unavailable:     return None (caller uses fallback label).
      - If N is not prd-labeled and has no parent: return None (non-PRD;
        caller routes to maintenance/non-PRD bucket, not phantom PRD node).

    Lookup order: disk cache → in-process cache → gh (write-through on hit).

    Returns int (parent PRD) or None (gh unavailable / unresolvable / non-PRD).

    Note (#1030): this function intentionally keeps the int|None contract —
    existing callers/tests distinguish only "resolved" vs "not resolved".
    Callers that need to distinguish "gh failed" from "genuinely non-PRD"
    (e.g. label text) should use _resolve_dispatch_to_prd_detailed() instead.
    """
    result, _gh_ok = _resolve_dispatch_to_prd_detailed(n)
    return result


def _read_subagent_meta(subagents_dir: Path) -> dict:
    """Read all agent-*.meta.json files in subagents_dir.

    Returns a dict keyed by toolUseId:
      {
        tool_use_id: {
          "agent_type":    str,   # from agentType field
          "description":   str,   # from description field
          "subagent_file": Path,  # path to the .jsonl file
          "meta_file":     Path,  # path to the .meta.json file
        }
      }

    Defensive: missing or malformed meta files are silently skipped.
    """
    result: dict = {}
    if not subagents_dir.is_dir():
        return result
    try:
        meta_files = [
            f for f in subagents_dir.iterdir()
            if f.is_file() and f.name.endswith(".meta.json")
        ]
    except Exception:
        return result

    for mf in meta_files:
        try:
            with mf.open(encoding="utf-8", errors="replace") as fh:
                meta = json.loads(fh.read())
            if not isinstance(meta, dict):
                continue
            tool_use_id = meta.get("toolUseId", "").strip()
            if not tool_use_id:
                continue
            # Derive the corresponding .jsonl file path
            stem = mf.name[: -len(".meta.json")]  # agent-<hex>
            jsonl_path = subagents_dir / (stem + ".jsonl")
            result[tool_use_id] = {
                "agent_type":    meta.get("agentType", ""),
                "description":   meta.get("description", ""),
                "subagent_file": jsonl_path,
                "meta_file":     mf,
            }
        except Exception:
            continue
    return result


def _parse_subagent_outcome(subagent_path: Path) -> dict:
    """Parse a subagent's JSONL to extract start/end timestamps and verdict.

    Returns:
      {
        "start": str,   # ISO timestamp of first record
        "end":   str,   # ISO timestamp of last assistant record
        "verdict": str, # VERDICT (APPROVE/BLOCK) or RESULT (SUCCESS/BLOCKED/…)
                        #  or "" if not found
      }

    Defensive: returns {"start":"","end":"","verdict":""} on any error.
    """
    empty: dict = {"start": "", "end": "", "verdict": ""}
    if not subagent_path.exists():
        return empty

    records = _read_jsonl_records(subagent_path)
    if not records:
        return empty

    # Start = timestamp of first record
    start = records[0].get("timestamp", "")

    # End + verdict = from last assistant message with text content
    end = ""
    verdict = ""
    for rec in reversed(records):
        ts = rec.get("timestamp", "")
        if ts and not end:
            end = ts
        if rec.get("type") == "assistant":
            msg = rec.get("message", {})
            if not isinstance(msg, dict):
                msg = {}
            content = msg.get("content", [])
            if not isinstance(content, list):
                content = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    text = item.get("text", "")
                    # Try VERDICT (critic subagents)
                    vm = _VERDICT_RE.search(text)
                    if vm:
                        verdict = vm.group(1).upper()
                        break
                    # Try RESULT (generator subagents like implementer)
                    rm = _RESULT_RE.search(text)
                    if rm:
                        verdict = rm.group(1).upper()
                        break
            if verdict:
                break

    return {"start": start, "end": end, "verdict": verdict}


def _derive_prd_label(description: str, agent_type: str, use_gh: bool = True) -> str:
    """Derive a PRD-bucket label from a dispatch description.

    When use_gh=True (default), attempts to resolve the first issue number
    in the description to its parent PRD via resolve_dispatch_to_prd().
    This maps slice/PR numbers to their parent PRD bucket so that all
    dispatches for a given PRD are grouped together (PRD #956 §2 #1).

    When gh is unavailable or use_gh=False, falls back to the raw #N label
    with a "(gh unavailable)" suffix — honest-empty per fallback AC.

    Fix (issue #1030): a genuinely-non-PRD issue (gh succeeded, no PRD
    parent found) now gets "#N (non-PRD)" instead of "#N (gh unavailable)" —
    the latter is reserved for actual gh transport failures, via
    _resolve_dispatch_to_prd_detailed()'s gh_ok flag.

    Strategy:
      1. Extract the first issue number #N from the description.
      2. (use_gh=True) Resolve N to its parent PRD via
         _resolve_dispatch_to_prd_detailed().
         - On success: label = "PRD #<parent>" to make it clear this is a PRD bucket.
         - On genuine non-PRD (gh_ok=True, result=None): label = "#N (non-PRD)".
         - On gh transport failure (gh_ok=False): label = "#N (gh unavailable)".
      3. (use_gh=False) label = "#N".
      4. If no issue number found: fall back to agent_type, then "unattributed".
    """
    if description:
        m = _ISSUE_RE.search(description)
        if m:
            raw_n = int(m.group(1))
            if use_gh:
                parent_prd, gh_ok = _resolve_dispatch_to_prd_detailed(raw_n)
                if parent_prd is not None:
                    return f"PRD #{parent_prd}"
                elif gh_ok:
                    # gh succeeded; issue genuinely has no PRD parent.
                    return f"#{raw_n} (non-PRD)"
                else:
                    # gh transport actually failed — honest fallback
                    return f"#{raw_n} (gh unavailable)"
            else:
                return f"#{raw_n}"
    if agent_type:
        return agent_type
    return "unattributed (this session)"


def _build_actor_map(main_path: Path, meta_map: dict) -> dict:
    """Build a tool_use_id → actor label map from the main transcript.

    Scans main_path for assistant records whose content contains Agent/Task
    tool_use items.  For each dispatch:
      - If the assistant record has no agentId: actor = "orchestrator"
      - If the assistant record has an agentId: look up that agentId stem in
        meta_map values to find the parent agent_type; actor = that type.
        Falls back to "orchestrator" when no mapping is found.

    Returns a dict {tool_use_id: actor_label}.
    Defensive: never raises; returns {} on error.
    """
    result: dict = {}
    if not main_path or not main_path.exists():
        return result

    # Build reverse map: agent_file_stem -> agent_type (for parent-lookup)
    # meta_map values have "subagent_file" = Path; stem is the agent-<hex> part
    stem_to_type: dict = {}
    for meta in meta_map.values():
        sub_path = meta.get("subagent_file")
        if sub_path:
            stem_to_type[Path(sub_path).stem] = meta.get("agent_type", "")

    records = _read_jsonl_records(main_path)
    for record in records:
        if record.get("type") != "assistant":
            continue
        agent_id = record.get("agentId", "")
        msg = record.get("message", {})
        if not isinstance(msg, dict):
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "tool_use":
                continue
            if item.get("name") not in ("Agent", "Task"):
                continue
            tid = item.get("id", "")
            if not tid:
                continue
            if agent_id:
                # This dispatch came from a subagent; find its type
                # agentId can be "agent-<hex>" or just the hex stem
                parent_type = (
                    stem_to_type.get(agent_id, "")
                    or stem_to_type.get(agent_id.replace("agent-", ""), "")
                    or agent_id
                )
                result[tid] = parent_type or "orchestrator"
            else:
                result[tid] = "orchestrator"

    return result


def _derive_tool_target(description: str, agent_type: str) -> str:
    """Derive the tool/target resource label for a firing row.

    Extracts the first issue/PR reference (#N or PR #N) from description.
    Falls back to a truncated description excerpt, then to agent_type.
    """
    if description:
        # Look for PR #N pattern first
        pr_m = _re.search(r"PR\s+#(\d+)", description, _re.IGNORECASE)
        if pr_m:
            return f"PR #{pr_m.group(1)}"
        # Then plain issue #N
        iss_m = _ISSUE_RE.search(description)
        if iss_m:
            return f"#{iss_m.group(1)}"
        # Fall back to first 40 chars of description
        return description[:40].strip()
    return agent_type or "unknown"


# Built-in Task agent types that go to research/other, not PRD/slice nodes
_TASK_RESEARCH_TYPES = frozenset({
    "explore", "plan", "general-purpose", "claude-code-guide",
    "task",  # plain Task tool calls (no subagent_type override)
})

_TASK_TOOL_NAME = frozenset({"Task", "task"})  # tool.name in transcript records


def _is_research_task(agent_type: str) -> bool:
    """Return True if agent_type is a built-in Task type → research/other bucket."""
    return agent_type.lower() in _TASK_RESEARCH_TYPES


def _get_prd_subissue_slices(prd_n: int) -> list[int]:
    """Fetch the slice sub-issue numbers for a PRD via gh CLI.

    Returns a list of sub-issue numbers (ints) labeled 'slice'.
    Returns [] if gh is unavailable or the PRD has no sub-issues.

    Uses gh issue view with --json subIssues to get the native GitHub
    sub-issue list. Falls back to [] gracefully on any error.
    """
    rc, stdout = _gh_run_transcript([
        "issue", "view", str(prd_n),
        "--json", "subIssues",
    ], timeout=15)
    if rc != 0 or not stdout.strip():
        return []
    try:
        data = json.loads(stdout)
    except Exception:
        return []
    sub_issues = (data.get("subIssues") or {}).get("nodes") or []
    if not isinstance(sub_issues, list):
        # Older gh CLI returns subIssues as a flat list (no .nodes wrapper)
        # Handle both shapes
        if isinstance(data.get("subIssues"), list):
            sub_issues = data["subIssues"]
        else:
            return []
    result: list[int] = []
    for node in sub_issues:
        if not isinstance(node, dict):
            continue
        n = node.get("number")
        labels = node.get("labels") or []
        if not isinstance(labels, list):
            continue
        label_names = {
            (lbl.get("name", "") if isinstance(lbl, dict) else str(lbl))
            for lbl in labels
        }
        # Accept if labeled 'slice', or if no labels field (graceful)
        if not labels or "slice" in label_names:
            if n:
                result.append(int(n))
    return result


def _count_transcript_firing_events(path: Path) -> int:
    """Count unique agent-dispatch events in the full transcript (deduped by tool_use_id).

    Parses both the main transcript and subagent transcripts (via parse_transcript),
    filters for event=="agent_start", dedupes by tool_use_id, and returns the count.

    This is the completeness denominator: the total distinct firing events the
    transcript recorded, regardless of whether subagent meta.json files exist.

    Defensive: returns 0 on error.
    """
    try:
        events = parse_transcript(path)
    except Exception:
        return 0
    seen_ids: set = set()
    for ev in events:
        if ev.get("event") != "agent_start":
            continue
        tid = ev.get("tool_use_id", "")
        if tid:
            seen_ids.add(tid)
        else:
            # No id — use ts+subagent_type as a surrogate key to avoid infinite counting
            seen_ids.add(f"{ev.get('ts','')}__{ev.get('subagent_type','')}")
    return len(seen_ids)


def build_firing_tree(path: Path) -> dict:
    """Build the per-PRD firing tree for the session at *path*.

    1. Reads meta.json files from the subagents directory to build a
       toolUseId → dispatch map.
    2. For each dispatch, parses the subagent JSONL to extract
       start/end/verdict.
    3. Groups dispatches by the PRD label derived from their description.
    4. Enriches each dispatch with actor, tool_target, outcome (slice #929).
    5. Computes completeness_count: unique agent_start events in full transcript
       (deduped by tool_use_id) for AC #6 completeness assertion.
    6. (slice #959) Builds a nested PRD→slice→dispatch structure with:
       - Task-type segregation (Explore/Plan/general-purpose → research_other)
       - Partial marker: PRD node is "partial" when gh sub-issues include slices
         whose dispatches are absent from this transcript.
       - Deduplication: each dispatch appears in exactly one leaf
         (deduped by tool_use_id across all nesting levels).

    Returns:
      {
        "groups": {                  # flat groups (backward-compat)
          "<prd-label>": [dispatch, …],
          …
        },
        "nested_groups": {           # nested PRD → slice → dispatch (slice #959)
          "<prd-label>": {
            "prd_n":    int | None,  # resolved PRD number, or None
            "partial":  bool,        # True when gh sub-issues have absent slices
            "slices": {
              "<slice-label>": [dispatch, …]
            },
            "unresolved": [dispatch, …],  # dispatches not matched to any slice
          },
          …
        },
        "research_other": [dispatch, …],  # built-in Task types (Explore/Plan/…)
        "dispatch_count":      int,
        "completeness_count":  int,
        "source": str,
        "error": str | None,
      }

    Defensive: never raises; returns error key on failure.
    """
    empty_result: dict = {
        "groups": {},
        "nested_groups": {},
        "research_other": [],
        "dispatch_count": 0,
        "completeness_count": 0,
        "source": str(path) if path else "",
        "error": None,
    }

    if not path or not path.exists():
        empty_result["error"] = "transcript path not found"
        return empty_result

    # Locate subagents directory: <session-id>/subagents/ next to main transcript
    subagents_dir = path.parent / path.stem / "subagents"

    meta_map = _read_subagent_meta(subagents_dir)

    # Completeness count: always computed from full transcript parse (deduped)
    completeness_count = _count_transcript_firing_events(path)

    if not meta_map:
        empty_result["source"] = str(path)
        empty_result["completeness_count"] = completeness_count
        # Not an error — session may have no subagent dispatches yet
        return empty_result

    # Build actor map: tool_use_id -> actor label
    actor_map = _build_actor_map(path, meta_map)

    # Build dispatch list; dedupe by tool_use_id
    groups: dict = {}
    research_other: list = []
    dispatch_count = 0
    seen_ids: set = set()

    # Collect all dispatches
    all_dispatches: list[dict] = []

    for tool_use_id, meta in meta_map.items():
        if tool_use_id in seen_ids:
            continue
        seen_ids.add(tool_use_id)

        agent_type   = meta["agent_type"]
        description  = meta["description"]
        sub_path     = meta["subagent_file"]

        outcome_data = _parse_subagent_outcome(sub_path)

        # Derive WHO fired this dispatch
        actor = actor_map.get(tool_use_id, "orchestrator") or "orchestrator"

        # Derive tool/target resource
        tool_target = _derive_tool_target(description, agent_type)

        # Derive outcome: use verdict if available, else "dispatched"
        raw_verdict = outcome_data["verdict"]
        outcome_str = raw_verdict if raw_verdict else "dispatched"

        dispatch = {
            "agent":       agent_type,
            "actor":       actor,
            "description": description,
            "tool_target": tool_target,
            "outcome":     outcome_str,
            "start":       outcome_data["start"],
            "end":         outcome_data["end"],
            "verdict":     raw_verdict,
            "tool_use_id": tool_use_id,
        }
        dispatch_count += 1

        # Task segregation: built-in Task types go to research_other
        if _is_research_task(agent_type):
            research_other.append(dispatch)
        else:
            label = _derive_prd_label(description, agent_type)
            if label not in groups:
                groups[label] = []
            groups[label].append(dispatch)

        all_dispatches.append(dispatch)

    # Sort dispatches within each group by start timestamp
    for label in groups:
        groups[label].sort(key=lambda d: d.get("start") or "")
    research_other.sort(key=lambda d: d.get("start") or "")

    # ---------------------------------------------------------------------------
    # Build nested_groups: PRD → slice → dispatch structure
    # ---------------------------------------------------------------------------
    nested_groups: dict = {}

    # For each PRD-labeled group, attempt to nest by slice sub-issue
    for label, dispatches in groups.items():
        # Extract PRD number from label ("PRD #956" -> 956)
        prd_n_match = _re.search(r"PRD\s+#(\d+)", label)
        prd_n: int | None = int(prd_n_match.group(1)) if prd_n_match else None

        # For each dispatch, derive the slice number it references
        # (the raw #N in the description, before PRD resolution)
        slice_buckets: dict[str, list] = {}
        unresolved: list = []

        for d in dispatches:
            desc = d.get("description", "")
            # Find the raw issue number from description
            raw_m = _ISSUE_RE.search(desc)
            raw_n = int(raw_m.group(1)) if raw_m else None

            # Determine slice label
            slice_label: str | None = None
            if raw_n is not None and prd_n is not None and raw_n != prd_n:
                # raw_n might be a slice or a PR — label it
                slice_label = f"#{raw_n}"
            elif raw_n is not None and raw_n == prd_n:
                # Dispatch references the PRD directly — place in unresolved
                slice_label = None

            if slice_label:
                if slice_label not in slice_buckets:
                    slice_buckets[slice_label] = []
                slice_buckets[slice_label].append(d)
            else:
                unresolved.append(d)

        # Sort dispatches within each slice bucket
        for sl in slice_buckets:
            slice_buckets[sl].sort(key=lambda d: d.get("start") or "")

        # Partial marker: check if any gh sub-issue slices are absent from
        # this transcript's dispatch set.
        partial = False
        if prd_n is not None:
            try:
                gh_slices = _get_prd_subissue_slices(prd_n)
                if gh_slices:
                    # Slices present in transcript: set of raw #N numbers in dispatches
                    transcript_slice_labels = set(slice_buckets.keys())
                    # Compare: any gh sub-issue slice NOT in transcript?
                    for gs in gh_slices:
                        if f"#{gs}" not in transcript_slice_labels:
                            partial = True
                            break
            except Exception:
                pass  # gh failure — leave partial=False (honest unknown)

        nested_groups[label] = {
            "prd_n":      prd_n,
            "partial":    partial,
            "slices":     slice_buckets,
            "unresolved": unresolved,
        }

    return {
        "groups": groups,
        "nested_groups": nested_groups,
        "research_other": research_other,
        "dispatch_count": dispatch_count,
        "completeness_count": completeness_count,
        "source": str(path),
        "error": None,
    }


# ---------------------------------------------------------------------------
# Mtime+size parse-cache for /api/session-firing (slice #997 / PRD #993 cr.6)
# ---------------------------------------------------------------------------
# Keyed on (path, mtime, size) so that:
#   - unchanged transcript (same path+mtime+size) → warm hit, returns in <1s
#   - any content change (mtime or size differs) → cold recompute
# Thread-safe: a lock guards the shared cache dict.
# ---------------------------------------------------------------------------

import threading as _threading  # imported here to avoid re-import at module level

_firing_cache: dict = {
    "path":   None,   # Path | None
    "mtime":  None,   # float | None
    "size":   None,   # int | None  — st_size added for (path, mtime, size) key
    "result": None,   # dict | None
}
_firing_cache_lock = _threading.Lock()

# ---------------------------------------------------------------------------
# Background-warm state for serve_session_firing() (issue #1061)
# Mirrors prd_firing._cache_computing (issue #962) — a single daemon thread
# builds the tree while the HTTP request path returns immediately.
# ---------------------------------------------------------------------------
_firing_cache_computing: bool = False


def get_session_firing() -> dict:
    """Return the firing tree dict for /api/session-firing.

    Parse-cache keyed on (transcript_path, mtime, size) — slice #997 / PRD #993 cr.6.
    A warm hit (unchanged transcript) returns the cached tree in <1s without
    re-invoking build_firing_tree().  Cache invalidates when either mtime or
    size changes (covers both timestamp-only and content-only updates).
    Thread-safe via _firing_cache_lock.
    """
    path = resolve_transcript()
    if path is None:
        return {
            "groups": {},
            "nested_groups": {},
            "research_other": [],
            "dispatch_count": 0,
            "source": "",
            "error": "no transcript file found",
        }

    try:
        st = path.stat()
        mtime = st.st_mtime
        size  = st.st_size
    except Exception as exc:
        return {
            "groups": {},
            "nested_groups": {},
            "research_other": [],
            "dispatch_count": 0,
            "source": str(path),
            "error": f"stat failed: {exc}",
        }

    # Warm-cache check (under lock so concurrent requests share the same result)
    with _firing_cache_lock:
        if (
            _firing_cache["path"]  == path
            and _firing_cache["mtime"] == mtime
            and _firing_cache["size"]  == size
        ):
            return _firing_cache["result"]  # type: ignore[return-value]

    # Cold path — recompute outside the lock (long-running; avoids blocking readers)
    result = build_firing_tree(path)

    with _firing_cache_lock:
        _firing_cache["path"]   = path
        _firing_cache["mtime"]  = mtime
        _firing_cache["size"]   = size
        _firing_cache["result"] = result
    return result


def _firing_background() -> None:
    """Build the firing tree in a background thread and populate _firing_cache.

    Called by serve_session_firing() on cold start / stale cache. Reuses the
    existing get_session_firing() (blocking) computation so the mtime+size
    cache-write logic (slice #997) is not duplicated. Always clears the
    computing flag in the finally block, even on failure.
    """
    global _firing_cache_computing
    try:
        get_session_firing()
    except Exception:
        pass  # get_session_firing() already returns honest-empty on error
    finally:
        with _firing_cache_lock:
            _firing_cache_computing = False


def serve_session_firing() -> dict:
    """Stale-while-revalidate serve path for /api/session-firing (issue #1061).

    ALWAYS returns immediately (target: <1s, typically <10ms):
      - Warm cache (transcript unchanged — same path/mtime/size): return
        cached tree.
      - Stale cache (transcript changed): return last-known tree with
        "refreshing": true and kick a background rebuild (if not already
        running).
      - Cold (no prior payload): return {"status": "computing"} and kick a
        background rebuild.

    Mirrors prd_firing.serve_prd_firing() (issue #962) and
    health.py::serve_health(). The mtime+size parse-cache (slice #997) only
    sped up WARM loads; this wrapper additionally takes the cold/first-hit
    cost off the request path entirely.
    """
    global _firing_cache_computing

    path = resolve_transcript()
    if path is None:
        return {
            "groups": {},
            "nested_groups": {},
            "research_other": [],
            "dispatch_count": 0,
            "source": "",
            "error": "no transcript file found",
        }

    try:
        st = path.stat()
        mtime = st.st_mtime
        size  = st.st_size
    except Exception as exc:
        return {
            "groups": {},
            "nested_groups": {},
            "research_other": [],
            "dispatch_count": 0,
            "source": str(path),
            "error": f"stat failed: {exc}",
        }

    with _firing_cache_lock:
        fresh = (
            _firing_cache["path"]  == path
            and _firing_cache["mtime"] == mtime
            and _firing_cache["size"]  == size
            and _firing_cache["result"] is not None
        )
        if fresh:
            # Cache matches current transcript state — serve immediately.
            return _firing_cache["result"]  # type: ignore[return-value]

        stale_result = _firing_cache["result"]

        if stale_result is not None:
            # Transcript changed since last build — serve stale + refresh.
            payload = dict(stale_result)
            payload["refreshing"] = True
            if not _firing_cache_computing:
                _firing_cache_computing = True
                t = _threading.Thread(target=_firing_background, daemon=True)
                t.start()
            return payload

        # No payload yet (true cold start) — kick background build if not
        # already running.
        if _firing_cache_computing:
            return {"status": "computing"}
        _firing_cache_computing = True

    # Start background thread outside the lock.
    t = _threading.Thread(target=_firing_background, daemon=True)
    t.start()
    return {"status": "computing"}


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
# Runtime reading cache for /api/runtime-reading
# ---------------------------------------------------------------------------

_runtime_cache: dict = {
    "path":   None,   # Path | None
    "mtime":  None,   # float | None
    "result": None,   # dict | None
}


def get_runtime_reading() -> dict:
    """Return a current-session runtime reading derived from the transcript.

    Uses the session-events cache (same mtime key as get_session_events) to
    avoid a full re-parse per request.

    Returns:
      {
        "source":       str,   # transcript file path (or "" when no transcript)
        "event_count":  int,   # total normalised events in transcript
        "session_age_s": float | None,  # seconds since first event timestamp
        "last_event_ts": str,  # ISO-8601 timestamp of most-recent event
        "last_event_type": str,  # event type of most-recent event (or "")
        "no_session":   bool,  # True when no transcript file was found
        "error":        str | None,
      }

    Legitimately returns no_session=True when there is no active transcript —
    per PRD #927 §6 rabbit-hole: "not observable" is correct when no session
    exists; only the false/incorrect cases are fixed by this function.
    """
    global _runtime_cache

    path = resolve_transcript()
    if path is None:
        return {
            "source": "",
            "event_count": 0,
            "session_age_s": None,
            "last_event_ts": "",
            "last_event_type": "",
            "no_session": True,
            "error": None,
        }

    try:
        mtime = path.stat().st_mtime
    except Exception as exc:
        return {
            "source": str(path),
            "event_count": 0,
            "session_age_s": None,
            "last_event_ts": "",
            "last_event_type": "",
            "no_session": False,
            "error": f"stat failed: {exc}",
        }

    # Cache hit
    if _runtime_cache["path"] == path and _runtime_cache["mtime"] == mtime:
        return _runtime_cache["result"]  # type: ignore[return-value]

    # Reuse (or trigger) the session-events cache for the parsed events
    session_data = get_session_events()
    events = session_data.get("events", [])
    parse_error = session_data.get("error")

    # Derive reading from events
    event_count = len(events)
    last_event_ts = ""
    last_event_type = ""
    session_age_s = None

    if events:
        first = events[0]
        last = events[-1]
        last_event_ts = last.get("ts", "")
        last_event_type = last.get("event", "")

        # Session age: now − first-event timestamp
        first_ts_str = first.get("ts", "")
        if first_ts_str:
            try:
                import time as _time
                from datetime import datetime as _dt
                first_dt = _dt.fromisoformat(first_ts_str.replace("Z", "+00:00"))
                session_age_s = round(_time.time() - first_dt.timestamp(), 1)
            except Exception:
                pass

    result = {
        "source": str(path),
        "event_count": event_count,
        "session_age_s": session_age_s,
        "last_event_ts": last_event_ts,
        "last_event_type": last_event_type,
        "no_session": False,
        "error": parse_error,
    }

    _runtime_cache["path"]   = path
    _runtime_cache["mtime"]  = mtime
    _runtime_cache["result"] = result
    return result


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


def _cli_firing() -> None:
    """Print the per-PRD firing tree from the current session transcript."""
    path = resolve_transcript()
    if path is None:
        print("ERROR: no transcript file found", file=sys.stderr)
        print(f"Searched: {_candidate_project_dirs()}", file=sys.stderr)
        sys.exit(1)

    print(f"Transcript path  : {path}")
    result = build_firing_tree(path)
    err = result.get("error")
    if err:
        print(f"Error            : {err}", file=sys.stderr)

    groups = result.get("groups", {})
    total = result.get("dispatch_count", 0)
    print(f"Dispatch count   : {total}")
    print(f"PRD buckets      : {len(groups)}")

    if not groups:
        print("(no dispatches found — subagents/ directory may be empty or missing)")
        sys.exit(0)

    print()
    for label in sorted(groups.keys()):
        dispatches = groups[label]
        print(f"  [{label}]  ({len(dispatches)} dispatch{'es' if len(dispatches) != 1 else ''})")
        for d in dispatches:
            start = (d.get("start") or "")[:19]
            end   = (d.get("end")   or "")[:19]
            agent   = (d.get("agent") or "?")[:20]
            verdict = d.get("verdict") or "—"
            desc    = (d.get("description") or "")[:60]
            print(f"    {start}  {agent:<20}  verdict={verdict:<10}  {desc}")
        print()

    sys.exit(0)


if __name__ == "__main__":
    if "--self" in sys.argv:
        _cli_self()
    elif "--firing" in sys.argv:
        _cli_firing()
    else:
        print("Usage: python dashboard/transcript.py --self | --firing")
        sys.exit(1)
